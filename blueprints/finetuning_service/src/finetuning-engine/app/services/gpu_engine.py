# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import torch
import logging
import os
import gc
import time
from typing import Dict, Optional, Callable
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments, TrainerCallback
from datasets import load_dataset
from app.config import settings

logger = logging.getLogger("uvicorn")

class GPUMonitor:
    """Monitor GPU usage and memory"""

    @staticmethod
    def get_gpu_memory_info() -> Dict:
        """Get current GPU memory usage including peak stats"""
        if not torch.cuda.is_available():
            return {"available": False}

        allocated = torch.cuda.memory_allocated(0) / (1024**3)
        reserved = torch.cuda.memory_reserved(0) / (1024**3)
        max_allocated = torch.cuda.max_memory_allocated(0) / (1024**3)
        total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        free = total - allocated

        return {
            "available": True,
            "allocated_gb": round(allocated, 2),
            "reserved_gb": round(reserved, 2),
            "max_allocated_gb": round(max_allocated, 2),
            "free_gb": round(free, 2),
            "total_gb": round(total, 2),
            "utilization_percent": round((allocated / total) * 100, 2)
        }

    @staticmethod
    def clear_gpu_memory():
        """Clear GPU cache, reset peak stats, and run garbage collection"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()  # Reset peak memory tracking
        gc.collect()
        logger.info("GPU memory cleared and peak stats reset")

class ProgressCallback(TrainerCallback):
    """Custom callback to track training progress and handle cancellation"""

    def __init__(self, job_id: int, update_callback: Optional[Callable] = None, cancellation_check: Optional[Callable] = None):
        self.job_id = job_id
        self.update_callback = update_callback
        self.cancellation_check = cancellation_check
        self.start_time = time.time()

    def on_step_end(self, args, state, control, **kwargs):
        """Check for cancellation after each training step"""
        if self.cancellation_check and self.cancellation_check(self.job_id):
            logger.warning(f"Job {self.job_id} - Cancellation requested, stopping training...")
            control.should_training_stop = True
            return control

    def on_log(self, args, state, control, logs=None, **kwargs):
        """Called when logging"""
        # Check for cancellation
        if self.cancellation_check and self.cancellation_check(self.job_id):
            logger.warning(f"Job {self.job_id} - Cancellation requested during logging")
            control.should_training_stop = True
            return control

        if logs and self.update_callback:
            elapsed_time = time.time() - self.start_time
            progress = {
                "current_step": state.global_step,
                "max_steps": state.max_steps,
                "loss": logs.get("loss", None),
                "learning_rate": logs.get("learning_rate", None),
                "elapsed_seconds": int(elapsed_time),
                "progress_percent": round((state.global_step / state.max_steps) * 100, 2) if state.max_steps else 0
            }
            self.update_callback(self.job_id, progress)
            logger.info(f"Job {self.job_id} - Step {state.global_step}/{state.max_steps} - Loss: {logs.get('loss', 'N/A')}")

def validate_gpu_availability() -> tuple[bool, str]:
    """Check if GPU is available and has sufficient memory"""
    if not torch.cuda.is_available():
        return False, "No GPU available"

    memory_info = GPUMonitor.get_gpu_memory_info()

    if not memory_info.get("available", False):
        return False, "GPU not available"

    # Format memory info as string
    memory_str = f"(Allocated: {memory_info['allocated_gb']}GB, Free: {memory_info['free_gb']}GB, Total: {memory_info['total_gb']}GB)"
    return True, f"GPU ready {memory_str}"

def execute_finetuning(
    model_name: str,
    data_path: str,
    output_dir: str,
    params: dict,
    job_id: Optional[int] = None,
    progress_callback: Optional[Callable] = None,
    cancellation_check: Optional[Callable] = None
) -> Dict:
    """
    Execute fine-tuning with comprehensive error handling and monitoring

    Args:
        model_name: HuggingFace model name or path
        data_path: Path to training data (JSON/JSONL)
        output_dir: Directory to save the fine-tuned model
        params: Hyperparameters dict
        job_id: Job ID for tracking
        progress_callback: Callback function for progress updates
        cancellation_check: Function to check if job should be cancelled
        progress_callback: Callback function for progress updates

    Returns:
        Dict with training results and metrics
    """
    start_time = time.time()

    try:
        # Validate GPU
        gpu_available, gpu_message = validate_gpu_availability()
        if not gpu_available:
            raise RuntimeError(gpu_message)

        logger.info(f"Starting Training Job {job_id}: {model_name}")
        logger.info(f"Data path: {data_path}")
        logger.info(f"Output dir: {output_dir}")
        logger.info(f"Parameters: {params}")

        # Clear GPU memory before starting
        GPUMonitor.clear_gpu_memory()
        initial_memory = GPUMonitor.get_gpu_memory_info()
        logger.info(f"Initial GPU memory: {initial_memory}")

        # Extract hyperparameters with defaults
        max_seq_length = params.get("max_seq_length", settings.DEFAULT_MAX_SEQ_LENGTH)
        batch_size = params.get("batch_size", settings.DEFAULT_BATCH_SIZE)
        gradient_accumulation = params.get("gradient_accumulation_steps", settings.DEFAULT_GRADIENT_ACCUMULATION)

        # Memory optimization warnings for Tesla T4 (14.5GB)
        if max_seq_length > 1024:
            logger.warning(f"max_seq_length={max_seq_length} may cause OOM on T4 GPU. Consider reducing to 1024 or less.")
        if batch_size > 1:
            logger.warning(f"batch_size={batch_size} may cause OOM on T4 GPU. Consider using batch_size=1 with gradient_accumulation={gradient_accumulation * batch_size}.")

        # Training duration: either num_train_epochs or max_steps (max_steps takes precedence)
        num_train_epochs = params.get("num_train_epochs", 3)
        max_steps = params.get("max_steps", None)
        #Keeping Max Steps as -1 to train full epochs if num_train_epochs is specified
        max_steps = -1

        learning_rate = params.get("learning_rate", 1e-5)
        warmup_steps = params.get("warmup_steps", 5)
        lora_r = params.get("lora_r", 16)
        lora_alpha = params.get("lora_alpha", 16)
        lora_dropout = params.get("lora_dropout", 0.05)
        target_modules = params.get("target_modules", ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])

        # Load model with Unsloth
        logger.info("Loading model with 4-bit quantization for memory efficiency Because of T4 GPU...")
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=max_seq_length,
            dtype=None,
            load_in_4bit=True,
            device_map="auto",
        )

        # Log memory usage after model load
        mem_after_load = GPUMonitor.get_gpu_memory_info()
        logger.info(f"GPU memory after model load: {mem_after_load['allocated_gb']:.2f}GB allocated, {mem_after_load['free_gb']:.2f}GB free")

        logger.info("Applying LoRA adapters with gradient checkpointing...")
        model = FastLanguageModel.get_peft_model(
            model,
            r=lora_r,
            target_modules=target_modules,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            bias="none",
            use_gradient_checkpointing="unsloth",  # Critical for memory efficiency
            random_state=3407,
        )

        # Log memory usage after LoRA adapters
        mem_after_lora = GPUMonitor.get_gpu_memory_info()
        logger.info(f"GPU memory after LoRA: {mem_after_lora['allocated_gb']:.2f}GB allocated, {mem_after_lora['free_gb']:.2f}GB free")

        # Load and validate dataset
        logger.info(f"Loading dataset from {data_path}...")
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Dataset file not found: {data_path}")

        dataset = load_dataset("json", data_files=data_path, split="train")
        logger.info(f"Dataset loaded: {len(dataset)} examples")

        EOS_TOKEN = tokenizer.eos_token # Must add EOS_TOKEN


        # Define formatting function for Alpaca-style datasets
        def formatting_prompts_func(examples):
            """Format instruction/input/output into a single text field"""
            instructions = examples.get("instruction", [])
            inputs = examples.get("input", [])
            outputs = examples.get("output", [])

            # Ensure all lists have the same length
            num_examples = len(instructions) if instructions else len(outputs)
            if not inputs:
                inputs = [""] * num_examples
            if not instructions:
                instructions = [""] * num_examples
            if not outputs:
                outputs = [""] * num_examples

            texts = []
            for instruction, input_text, output in zip(instructions, inputs, outputs):
                text = f"### Instruction:\n{instruction}\n\n"
                if input_text:
                    text += f"### Input:\n{input_text}\n\n"
                text += f"### Response:\n{output}{EOS_TOKEN}"
                texts.append(text)
            return texts

        # Determine if we need a formatting function
        dataset_text_field = params.get("dataset_text_field", "text")
        formatting_func = None

        # Check if dataset has Alpaca format (instruction/input/output)
        if "instruction" in dataset.column_names and "output" in dataset.column_names:
            logger.info("Detected Alpaca-style dataset format (instruction/input/output)")
            formatting_func = formatting_prompts_func
            dataset_text_field = None  # Don't use text field when using formatting_func
        elif dataset_text_field not in dataset.column_names:
            # Try to find a suitable field
            possible_fields = ["text", "prompt", "input", "content"]
            found_field = None
            for field in possible_fields:
                if field in dataset.column_names:
                    found_field = field
                    break
            if found_field:
                dataset_text_field = found_field
                logger.warning(f"Using '{dataset_text_field}' as text field")
            else:
                raise ValueError(f"Could not find text field in dataset. Available fields: {dataset.column_names}")

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        training_output_dir = os.path.join(output_dir, "checkpoints")

        # Setup trainer with aggressive memory optimizations
        effective_batch_size = batch_size * gradient_accumulation
        logger.info(f"Setting up trainer with effective batch size: {effective_batch_size} (batch_size={batch_size} × gradient_accumulation={gradient_accumulation})")

        trainer_kwargs = {
            "model": model,
            "tokenizer": tokenizer,
            "train_dataset": dataset,
            "max_seq_length": max_seq_length,
            "dataset_num_proc": 4, # Use multiple processes for data loading
            "packing": False,  # Packing can increase memory usage
            "args": TrainingArguments(
                per_device_train_batch_size=batch_size,
                gradient_accumulation_steps=gradient_accumulation,
                warmup_steps=warmup_steps,
                num_train_epochs=num_train_epochs if num_train_epochs is not None else 3,
                max_steps=max_steps if max_steps is not None else -1,
                learning_rate=learning_rate,
                fp16=not torch.cuda.is_bf16_supported(),
                bf16=torch.cuda.is_bf16_supported(),
                logging_steps=1,
                optim="adamw_8bit",  # 8-bit optimizer saves memory
                weight_decay=0.01,
                lr_scheduler_type="linear",
                seed=3407,
                output_dir=training_output_dir,
                save_strategy="epoch" if max_steps < 0 else ("steps" if max_steps > 100 else "no"),  # In our case this will be applied
                save_steps=max(max_steps // 4, 1) if max_steps > 100 else 999999,
                save_total_limit=2,
                # Memory optimization flags
                gradient_checkpointing=True,  # Critical for reducing memory
                max_grad_norm=0.3,  # Gradient clipping
                dataloader_pin_memory=False,  # Reduce pinned memory usage
            ),
            "callbacks": [ProgressCallback(job_id, progress_callback, cancellation_check)] if job_id else [],
        }

        # Add either formatting_func or dataset_text_field
        if formatting_func:
            trainer_kwargs["formatting_func"] = formatting_func
        else:
            trainer_kwargs["dataset_text_field"] = dataset_text_field

        trainer = SFTTrainer(**trainer_kwargs)

        # Clear memory cache before training
        GPUMonitor.clear_gpu_memory()
        mem_before_train = GPUMonitor.get_gpu_memory_info()
        logger.info(f"GPU memory before training: {mem_before_train['allocated_gb']:.2f}GB allocated, {mem_before_train['free_gb']:.2f}GB free")

        # Start training
        logger.info("Starting training...")
        logger.info(f"Effective batch size: {batch_size * gradient_accumulation}, Max seq length: {max_seq_length}")
        train_result = trainer.train()

        # Save model
        logger.info(f"Saving model to {output_dir}...")
        # This is to save lora adapter
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)

        # This is to save model for vLLM ready - vivek

        model.save_pretrained_merged(output_dir, tokenizer, save_method = "merged_16bit")

        # Save training arguments for reproducibility
        with open(os.path.join(output_dir, "training_args.json"), "w") as f:
            import json
            json.dump(params, f, indent=2)

        # Get final metrics including peak memory usage
        final_memory = GPUMonitor.get_gpu_memory_info()
        elapsed_time = time.time() - start_time

        logger.info(f"Peak GPU memory during training: {final_memory.get('max_allocated_gb', 'N/A')}GB")

        results = {
            "success": True,
            "model_path": output_dir,
            "training_loss": train_result.training_loss if hasattr(train_result, 'training_loss') else None,
            "total_steps": train_result.global_step if hasattr(train_result, 'global_step') else (max_steps if max_steps > 0 else None),
            "num_train_epochs": num_train_epochs,
            "max_steps_requested": max_steps if max_steps > 0 else None,
            "elapsed_seconds": int(elapsed_time),
            "elapsed_hours": round(elapsed_time / 3600, 2),
            "initial_memory_gb": initial_memory,
            "final_memory_gb": final_memory,
            "peak_memory_gb": final_memory.get('max_allocated_gb'),
            "dataset_size": len(dataset)
        }

        logger.info(f"Training completed successfully in {elapsed_time/60:.2f} minutes")
        logger.info(f"Results: {results}")

        # Clean up
        GPUMonitor.clear_gpu_memory()

        return results

    except Exception as e:
        logger.error(f"Training failed: {str(e)}", exc_info=True)
        GPUMonitor.clear_gpu_memory()
        raise RuntimeError(f"Training failed: {str(e)}") from e
