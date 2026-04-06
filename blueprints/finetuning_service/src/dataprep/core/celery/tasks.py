import io
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from celery import chord, group
from llama_index.core import SimpleDirectoryReader
from llama_index.core.llama_dataset.generator import RagDatasetGenerator
from llama_index.llms.openai_like import OpenAILike
from llama_index.readers.file import MarkdownReader

from core.celery.celery_config import celery_app
from core.config.database import SessionLocal
from core.handlers.metadata_handler import MetadataHandler
from core.handlers.storage_handler import StorageHandler
from core.utils.database_utils import get_filename_with_extension, get_file_metadata

logger = logging.getLogger(__name__)

@celery_app.task(name='core.celery.tasks.process_file_with_docling', bind=False, queue='dataprep_queue')
def process_file_with_docling(
    file_id: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Download file from MinIO and convert to markdown using Docling.

    Args:
        file_id: Unique file identifier in MinIO
        user_id: User identifier to construct object path

    Returns:
        Dictionary containing:
        - file_id: Original file ID
        - markdown_file_id: ID of markdown file in MinIO
        - status: 'completed' or 'failed'
        - message: Status message
    """
    try:
        # Initialize storage handler
        storage = StorageHandler()

        # Construct object name with user_id path
        object_name = f"{user_id}/{file_id}"

        # Check if file exists in MinIO
        if not storage.file_exists(object_name):
            return {
                'file_id': file_id,
                'status': 'failed',
                'message': f'File {file_id} not found in storage'
            }

        # Create temporary directory for processing
        temp_dir = tempfile.mkdtemp(prefix=f"docling_{file_id}_")
        logger.info(f"Processing file {file_id} in temp directory: {temp_dir}")

        # Get filename and extension from PostgreSQL
        metadata = get_file_metadata(file_id, user_id)
        if not metadata:
            return {
                'file_id': file_id,
                'status': 'failed',
                'message': f'File metadata not found in database for {file_id}'
            }

        original_filename = metadata.get('filename', file_id)
        logger.info(f"Original filename from database: {original_filename}")

        # Download file from MinIO to temp directory
        logger.info(f"Downloading file {file_id} from MinIO...")
        file_stream = storage.get_file_stream(object_name)
        if not file_stream:
            return {
                'file_id': file_id,
                'status': 'failed',
                'message': f'Failed to download file {file_id} from MinIO or S3'
            }

        # Save downloaded file to temp directory with ORIGINAL filename
        input_file_path = Path(temp_dir) / original_filename
        with open(input_file_path, 'wb') as f:
            f.write(file_stream.read())
        file_stream.close()

        logger.info(f"File downloaded and saved to {input_file_path}")

        file_extension = Path(original_filename).suffix.lower()
        if file_extension == '.txt':
            logger.info(f"TXT file detected - converting to markdown...")
            with open(input_file_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
        else:
            from docling.document_converter import DocumentConverter, PdfFormatOption, WordFormatOption, PowerpointFormatOption
            from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions, AcceleratorOptions
            from docling.datamodel.base_models import InputFormat
            from docling_core.types.doc import ImageRefMode
            from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

            logger.info(f"Converting document using Docling...")
            # Configure PDF pipeline options
            options = PdfPipelineOptions()
            options.do_ocr = False
            num_threads = int(os.getenv('DOCLING_NUM_THREADS', '24'))
            options.accelerator_options = AcceleratorOptions(num_threads=num_threads)
            options.generate_picture_images = False
            options.generate_page_images = False
            options.do_table_structure = True

            # Create document converter
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=options, backend=PyPdfiumDocumentBackend),
                    InputFormat.DOCX: WordFormatOption(),
                    InputFormat.PPTX: PowerpointFormatOption()
                }
            )

            result = converter.convert(str(input_file_path))
            markdown_content = result.document.export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)

        # Generate markdown file ID
        filename_without_ext = Path(original_filename).stem
        markdown_file_id = f"{filename_without_ext}_markdown"
        markdown_object_name = f"{user_id}/processed/{markdown_file_id}.md"

        # Upload markdown to MinIO or S3
        logger.info(f"Uploading markdown to MinIO or S3 as {markdown_object_name}...")
        markdown_bytes = markdown_content.encode('utf-8')
        success = storage.upload_file(
            file_id=markdown_object_name,
            file_data=io.BytesIO(markdown_bytes),
            file_size=len(markdown_bytes),
            content_type='text/markdown'
        )

        if not success:
            return {
                'file_id': file_id,
                'status': 'failed',
                'message': 'Failed to upload markdown to MinIO or S3'
            }

        with SessionLocal() as db:
            metadata_handler = MetadataHandler(db=db)
            markdown_metadata = {
                "id": markdown_file_id,
                "object": "file",
                "bytes": len(markdown_bytes),
                "created_at": int(datetime.now().timestamp()),
                "filename": f"{markdown_file_id}.md",
                "purpose": "intermediate_processing",
                "status": "processed",
                "status_details": None,
                "user_id": user_id,
                "source_file_id": file_id,
                "file_type": "markdown"
            }
            metadata_handler.add(markdown_file_id, markdown_metadata, user_id)

        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Warning: Failed to clean up temp directory: {str(e)}")

        logger.info(f"Successfully converted and uploaded markdown for {file_id}")
        return {
            'file_id': file_id,
            'markdown_file_id': markdown_file_id,
            'status': 'completed',
            'message': 'Successfully converted file to markdown using Docling'
        }

    except Exception as e:
        logger.error(f"Error processing file {file_id} with Docling: {str(e)}")
        return {
            'file_id': file_id,
            'status': 'failed',
            'message': f'Error processing file with Docling: {str(e)}'
        }


@celery_app.task(name='core.celery.tasks.generate_qa_pairs_from_markdown', bind=False, queue='dataprep_queue')
def generate_qa_pairs_from_markdown(
    docling_result: Dict[str, Any],
    user_id: str
) -> Dict[str, Any]:
    """
    Generate QA pairs from markdown file using LlamaIndex.

    Args:
        docling_result: Result from docling processing task
        user_id: User identifier to construct object path

    Returns:
        Dictionary containing:
        - file_id: Original file ID
        - qa_file_id: ID of QA pairs file in MinIO
        - qa_pairs_count: Number of QA pairs generated
        - status: 'completed' or 'failed'
        - message: Status message
    """
    try:
        # Check if docling processing was successful
        if docling_result.get('status') != 'completed':
            return {
                'file_id': docling_result.get('file_id'),
                'status': 'failed',
                'message': f"Docling processing failed: {docling_result.get('message')}"
            }

        file_id = docling_result['file_id']
        markdown_file_id = docling_result['markdown_file_id']

        logger.info(f"Generating QA pairs from markdown for file {file_id}")

        # Initialize storage handler
        storage = StorageHandler()

        # Download markdown file from MinIO
        markdown_object_name = f"{user_id}/processed/{markdown_file_id}.md"
        markdown_stream = storage.get_file_stream(markdown_object_name)
        if not markdown_stream:
            return {
                'file_id': file_id,
                'status': 'failed',
                'message': 'Failed to download markdown file from MinIO'
            }

        # Create temporary directory for processing
        temp_dir = tempfile.mkdtemp(prefix=f"qa_{file_id}_")
        markdown_file_path = Path(temp_dir) / f"{markdown_file_id}.md"

        with open(markdown_file_path, 'wb') as f:
            f.write(markdown_stream.read())
        markdown_stream.close()

        logger.info(f"Downloaded markdown file to {markdown_file_path}")

        # Generate QA pairs using LlamaIndex
        try:
            logger.info(f"Generating QA pairs using LlamaIndex...")

            # Load markdown using LlamaIndex
            file_extractor = {".md": MarkdownReader()}
            documents = SimpleDirectoryReader(
                input_files=[str(markdown_file_path)],
                file_extractor=file_extractor
            ).load_data()

            logger.info(f"Loaded markdown document ({len(documents[0].get_content())} chars)")

            # Initialize LLM with OpenAI-like endpoint
            api_base = os.getenv('LLM_API_BASE', '')
            model = os.getenv('LLM_MODEL_ID', '')
            api_key = os.getenv('LLM_API_KEY', '')

            if not api_key:
                logger.warning("Warning: LLM_API_KEY not set, skipping QA generation")
                return {
                    'file_id': file_id,
                    'status': 'failed',
                    'message': 'LLM_API_KEY not set'
                }

            logger.info(f"Connecting to vLLM endpoint: {api_base}")
            llm = OpenAILike(
                model=model,
                api_base=api_base,
                api_key=api_key,
                context_window=int(os.getenv('MODEL_CONTEXT_WINDOW', '32000')),
                is_chat_model=True,
                is_function_calling_model=False,
                temperature=0.1
            )

            # Generate QA pairs
            logger.info("Generating QA pairs...")
            generator = RagDatasetGenerator.from_documents(
                documents,
                llm=llm,
                num_questions_per_chunk=int(os.getenv('QA_PER_DATASET_CHUNKS', '10')),
                show_progress=False
            )

            rag_dataset = generator.generate_dataset_from_nodes()

            # Filter and convert QA pairs
            meta_patterns = [
                "here are", "20 questions", "haven't provided", "please go ahead",
                "please provide", "i'll answer", "however, you haven't", "you haven't",
                "i'll do my best", "go ahead and provide", "file path of the document",
                "what is the file path", "title of the file", "filename", "document being referred", ".md"
            ]

            qa_pairs = []
            for example in rag_dataset.examples:
                question = example.query.strip()
                answer = example.reference_answer.strip()

                is_meta = any(pattern.lower() in question.lower()[:150] for pattern in meta_patterns)

                if not is_meta and len(question) > 15 and len(answer) > 20:
                    qa_pairs.append({
                        "question": question,
                        "answer": answer,
                        "source_file_id": file_id
                    })

            logger.info(f"Generated {len(qa_pairs)} QA pairs")

            # Create JSONL content
            jsonl_content = '\n'.join(json.dumps(pair) for pair in qa_pairs)

            # Generate QA file ID
            filename_without_ext = Path(file_id).stem if '.' in file_id else file_id
            qa_file_id = f"{filename_without_ext}_qa"
            qa_object_name = f"{user_id}/processed/{qa_file_id}.jsonl"

            # Upload JSONL to MinIO
            logger.info(f"Uploading QA JSONL to MinIO as {qa_object_name}...")
            jsonl_bytes = jsonl_content.encode('utf-8')
            success = storage.upload_file(
                file_id=qa_object_name,
                file_data=io.BytesIO(jsonl_bytes),
                file_size=len(jsonl_bytes),
                content_type='application/jsonl'
            )

            if not success:
                return {
                    'file_id': file_id,
                    'status': 'failed',
                    'message': 'Failed to upload QA JSONL to MinIO'
                }

            # Save metadata for the QA file
            with SessionLocal() as db:
                metadata_handler = MetadataHandler(db=db)
                qa_metadata = {
                    "id": qa_file_id,
                    "object": "file",
                    "bytes": len(jsonl_bytes),
                    "created_at": int(datetime.now().timestamp()),
                    "filename": f"{qa_file_id}.jsonl",
                    "purpose": "training_data",
                    "status": "processed",
                    "status_details": None,
                    "user_id": user_id,
                    "source_file_id": file_id,
                    "file_type": "qa_pairs",
                    "qa_pairs_count": len(qa_pairs)
                }
                metadata_handler.add(qa_file_id, qa_metadata, user_id)

            # Cleanup temporary directory
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Warning: Failed to clean up temp directory: {str(e)}")

            return {
                'file_id': file_id,
                'qa_file_id': qa_file_id,
                'qa_pairs_count': len(qa_pairs),
                'status': 'completed',
                'message': f'Successfully generated {len(qa_pairs)} QA pairs'
            }

        except Exception as e:
            logger.error(f"Error generating QA pairs: {str(e)}")
            return {
                'file_id': file_id,
                'status': 'failed',
                'message': f'Error generating QA pairs: {str(e)}'
            }

    except Exception as e:
        logger.error(f"Error in QA generation task: {str(e)}")
        return {
            'file_id': docling_result.get('file_id', 'unknown'),
            'status': 'failed',
            'message': f'Error in QA generation task: {str(e)}'
        }



@celery_app.task(name='core.celery.tasks.aggregate_qa_results', bind=False, queue='dataprep_queue')
def aggregate_qa_results(
    qa_results: List[Dict[str, Any]],
    user_id: str,
    original_file_ids: List[str]
) -> Dict[str, Any]:
    """
    Aggregate QA results from multiple file processing tasks.
    Combines all QA pairs into a single JSONL file and uploads to MinIO.

    Args:
        qa_results: List of results from QA generation tasks
        user_id: User identifier for file path
        original_file_ids: Original list of file IDs that were processed

    Returns:
        Dictionary containing:
        - aggregated_file_id: ID of the combined QA file in MinIO
        - total_qa_pairs: Total number of QA pairs aggregated
        - successful_files: Number of files processed successfully
        - failed_files: Number of files that failed processing
        - status: 'completed' or 'failed'
        - message: Status message
    """
    try:
        logger.info(f"Aggregating results from {len(qa_results)} QA generation tasks")

        storage = StorageHandler()

        successful_results = [r for r in qa_results if r.get('status') == 'completed']
        failed_results = [r for r in qa_results if r.get('status') == 'failed']

        logger.info(f"Successful: {len(successful_results)}, Failed: {len(failed_results)}")

        if not successful_results:
            return {
                'status': 'failed',
                'message': 'No files were processed successfully',
                'successful_files': 0,
                'failed_files': len(failed_results),
                'total_qa_pairs': 0
            }

        # Collect all QA pairs from successful results
        all_qa_pairs = []
        source_files = []

        for result in successful_results:
            file_id = result.get('file_id')
            qa_file_id = result.get('qa_file_id')

            if qa_file_id:
                source_files.append(file_id)

                # Download the QA JSONL file from MinIO
                qa_object_name = f"{user_id}/processed/{qa_file_id}.jsonl"

                try:
                    qa_stream = storage.get_file_stream(qa_object_name)
                    if qa_stream:
                        qa_content = qa_stream.read().decode('utf-8')
                        qa_stream.close()

                        # Parse JSONL and add additional metadata
                        for line in qa_content.strip().split('\n'):
                            if line:
                                qa_pair = json.loads(line)
                                qa_pair['qa_file_id'] = qa_file_id
                                all_qa_pairs.append(qa_pair)

                except Exception as e:
                    logger.warning(f"Warning: Failed to download QA file for {file_id}: {str(e)}")
                    continue

        logger.info(f"Collected {len(all_qa_pairs)} QA pairs from {len(source_files)} files")

        if not all_qa_pairs:
            return {
                'status': 'failed',
                'message': 'No QA pairs found in processed files',
                'successful_files': len(successful_results),
                'failed_files': len(failed_results),
                'total_qa_pairs': 0
            }

        # Convert QA pairs to Alpaca format
        alpaca_formatted_pairs = []
        for qa_pair in all_qa_pairs:
            alpaca_pair = {
                "instruction": qa_pair.get('question', ''),
                "input": "",
                "output": qa_pair.get('answer', '')
            }
            alpaca_formatted_pairs.append(alpaca_pair)

        # Create aggregated JSON array content in Alpaca format
        aggregated_content = json.dumps(alpaca_formatted_pairs, indent=2)

        # Generate aggregated file ID (with .jsonl extension)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        aggregated_file_id = f"aggregated_qa_{timestamp}.jsonl"
        aggregated_object_name = f"{user_id}/{aggregated_file_id}"

        # Upload aggregated JSONL to MinIO
        logger.info(f"Uploading aggregated QA file to MinIO as {aggregated_object_name}...")
        file_bytes = aggregated_content.encode('utf-8')
        success = storage.upload_file(
            file_id=aggregated_object_name,
            file_data=io.BytesIO(file_bytes),
            file_size=len(file_bytes),
            content_type='application/jsonl'
        )

        if not success:
            return {
                'status': 'failed',
                'message': 'Failed to upload aggregated QA file to MinIO',
                'successful_files': len(successful_results),
                'failed_files': len(failed_results),
                'total_qa_pairs': len(all_qa_pairs)
            }

        # Save metadata for the aggregated file
        with SessionLocal() as db:
            metadata_handler = MetadataHandler(db=db)
            aggregated_metadata = {
                "id": aggregated_file_id,
                "object": "file",
                "bytes": len(file_bytes),
                "created_at": int(datetime.now().timestamp()),
                "filename": aggregated_file_id,
                "purpose": "training_data",
                "status": "processed",
                "status_details": None,
                "user_id": user_id,
                "source_file_ids": original_file_ids,
                "successful_source_files": source_files,
                "processing_type": "aggregated_qa_pairs",
                "file_type": "aggregated_qa_pairs",
                "total_qa_pairs": len(all_qa_pairs),
                "source_file_count": len(source_files)
            }
            metadata_handler.add(aggregated_file_id, aggregated_metadata, user_id)

        logger.info(f"Successfully aggregated {len(all_qa_pairs)} QA pairs from {len(source_files)} files")

        return {
            'aggregated_file_id': aggregated_file_id,
            'total_qa_pairs': len(all_qa_pairs),
            'successful_files': len(successful_results),
            'failed_files': len(failed_results),
            'source_files': source_files,
            'original_file_ids': original_file_ids,
            'status': 'completed',
            'message': f'Successfully aggregated {len(all_qa_pairs)} QA pairs from {len(source_files)} files'
        }

    except Exception as e:
        logger.error(f"Error in aggregation: {str(e)}")
        return {
            'status': 'failed',
            'message': f'Error during aggregation: {str(e)}',
            'successful_files': len(successful_results) if 'successful_results' in locals() else 0,
            'failed_files': len(failed_results) if 'failed_results' in locals() else 0,
            'total_qa_pairs': len(all_qa_pairs) if 'all_qa_pairs' in locals() else 0
        }


@celery_app.task(name='core.celery.tasks.dataset_generation_using_data_kits', bind=True, queue='dataprep_queue')
def dataset_generation_using_data_kits(
    self,
    file_ids: List[str],
    user_id: str
) -> Dict[str, Any]:
    """
    Generate training dataset from multiple files using parallel processing.

    Process flow:
    1. For each file: Download + Docling conversion (parallel)
    2. Chain to: Generate QA pairs from markdown (parallel)
    3. Chord to: Aggregate all QA pairs into single JSONL

    Args:
        file_ids: List of unique file identifiers in MinIO
        user_id: User identifier to construct object path

    Returns:
        Dictionary containing:
        - chord_id: Chord job identifier
        - file_ids: List of file IDs being processed
        - status: 'executing' or 'failed'
        - message: Status message
    """
    try:
        logger.info(f"Starting processing of {len(file_ids)} files for user {user_id}")


        file_processing_chains = [
            (process_file_with_docling.s(file_id=file_id, user_id=user_id) |
             generate_qa_pairs_from_markdown.s(user_id=user_id))
            for file_id in file_ids
        ]

        # Create callback for aggregation
        callback = aggregate_qa_results.s(
            user_id=user_id,
            original_file_ids=file_ids
        )

        logger.info(f"Creating chord with {len(file_processing_chains)} chains")
        workflow = chord(file_processing_chains)(callback)
        logger.info(f"Chord executed! Result ID: {workflow.id}")

        # Get child task IDs from the workflow for progress tracking
        # The workflow.parent contains the GroupResult with all chain task IDs
        child_task_ids = []
        if hasattr(workflow, 'parent') and workflow.parent:
            child_task_ids = [child.id for child in workflow.parent.results]

        logger.info(f"Child task IDs: {child_task_ids}")

        # Update parent task state for tracking
        self.update_state(state='PROGRESS', meta={
            'current': 0,
            'total': len(file_ids),
            'status': 'Processing files in parallel',
            'chord_id': workflow.id,
            'child_task_ids': child_task_ids
        })

        logger.info(f"Chord workflow dispatched - tasks should now execute on workers")

        return {
            'chord_id': workflow.id,
            'child_task_ids': child_task_ids,
            'file_ids': file_ids,
            'file_count': len(file_ids),
            'user_id': user_id,
            'status': 'executing',
            'message': f'Parallel processing chord started for {len(file_ids)} files'
        }

    except Exception as e:
        logger.error(f"Error starting parallel processing for user {user_id}: {str(e)}")
        self.update_state(state='FAILURE', meta=str(e))
        return {
            'file_ids': file_ids,
            'user_id': user_id,
            'status': 'failed',
            'message': f'Error starting parallel processing: {str(e)}'
        }


@celery_app.task(name='core.celery.tasks.aggregate_qa_results', bind=False, queue='dataprep_queue')
def aggregate_qa_results(
    qa_results: List[Dict[str, Any]],
    user_id: str,
    original_file_ids: List[str]
) -> Dict[str, Any]:
    """
    Aggregate QA results from multiple file processing tasks.
    Combines all QA pairs into a single JSONL file and uploads to MinIO.

    Args:
        qa_results: List of results from QA generation tasks
        user_id: User identifier for file path
        original_file_ids: Original list of file IDs that were processed

    Returns:
        Dictionary containing:
        - aggregated_file_id: ID of the combined QA file in MinIO
        - total_qa_pairs: Total number of QA pairs aggregated
        - successful_files: Number of files processed successfully
        - failed_files: Number of files that failed processing
        - status: 'completed' or 'failed'
        - message: Status message
    """
    try:
        logger.info(f"Aggregating results from {len(qa_results)} QA generation tasks")

        storage = StorageHandler()

        successful_results = [r for r in qa_results if r.get('status') == 'completed']
        failed_results = [r for r in qa_results if r.get('status') == 'failed']

        logger.info(f"Successful: {len(successful_results)}, Failed: {len(failed_results)}")

        if not successful_results:
            return {
                'status': 'failed',
                'message': 'No files were processed successfully',
                'successful_files': 0,
                'failed_files': len(failed_results),
                'total_qa_pairs': 0
            }

        # Collect all QA pairs from successful results
        all_qa_pairs = []
        source_files = []

        for result in successful_results:
            file_id = result.get('file_id')
            qa_file_id = result.get('qa_file_id')

            if qa_file_id:
                source_files.append(file_id)

                # Download the QA JSONL file from MinIO
                qa_object_name = f"{user_id}/processed/{qa_file_id}.jsonl"

                try:
                    qa_stream = storage.get_file_stream(qa_object_name)
                    if qa_stream:
                        qa_content = qa_stream.read().decode('utf-8')
                        qa_stream.close()

                        # Parse JSONL and add additional metadata
                        for line in qa_content.strip().split('\n'):
                            if line:
                                qa_pair = json.loads(line)
                                qa_pair['qa_file_id'] = qa_file_id
                                all_qa_pairs.append(qa_pair)

                except Exception as e:
                    logger.warning(f"Warning: Failed to download QA file for {file_id}: {str(e)}")
                    continue

        logger.info(f"Collected {len(all_qa_pairs)} QA pairs from {len(source_files)} files")

        if not all_qa_pairs:
            return {
                'status': 'failed',
                'message': 'No QA pairs found in processed files',
                'successful_files': len(successful_results),
                'failed_files': len(failed_results),
                'total_qa_pairs': 0
            }

        # Convert QA pairs to Alpaca format
        alpaca_formatted_pairs = []
        for qa_pair in all_qa_pairs:
            alpaca_pair = {
                "instruction": qa_pair.get('question', ''),
                "input": "",
                "output": qa_pair.get('answer', '')
            }
            alpaca_formatted_pairs.append(alpaca_pair)

        # Create aggregated JSON array content in Alpaca format
        aggregated_content = json.dumps(alpaca_formatted_pairs, indent=2)

        # Generate aggregated file ID (with .jsonl extension)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        aggregated_file_id = f"aggregated_qa_{timestamp}.jsonl"
        aggregated_object_name = f"{user_id}/{aggregated_file_id}"

        # Upload aggregated JSONL to MinIO
        logger.info(f"Uploading aggregated QA file to MinIO as {aggregated_object_name}...")
        file_bytes = aggregated_content.encode('utf-8')
        success = storage.upload_file(
            file_id=aggregated_object_name,
            file_data=io.BytesIO(file_bytes),
            file_size=len(file_bytes),
            content_type='application/jsonl'
        )

        if not success:
            return {
                'status': 'failed',
                'message': 'Failed to upload aggregated QA file to MinIO',
                'successful_files': len(successful_results),
                'failed_files': len(failed_results),
                'total_qa_pairs': len(all_qa_pairs)
            }

        # Save metadata for the aggregated file
        with SessionLocal() as db:
            metadata_handler = MetadataHandler(db=db)
            aggregated_metadata = {
                "id": aggregated_file_id,
                "object": "file",
                "bytes": len(file_bytes),
                "created_at": int(datetime.now().timestamp()),
                "filename": aggregated_file_id,
                "purpose": "training_data",
                "status": "processed",
                "status_details": None,
                "user_id": user_id,
                "source_file_ids": original_file_ids,
                "successful_source_files": source_files,
                "processing_type": "aggregated_qa_pairs",
                "file_type": "aggregated_qa_pairs",
                "total_qa_pairs": len(all_qa_pairs),
                "source_file_count": len(source_files)
            }
            metadata_handler.add(aggregated_file_id, aggregated_metadata, user_id)

        logger.info(f"Successfully aggregated {len(all_qa_pairs)} QA pairs from {len(source_files)} files")

        return {
            'aggregated_file_id': aggregated_file_id,
            'total_qa_pairs': len(all_qa_pairs),
            'successful_files': len(successful_results),
            'failed_files': len(failed_results),
            'source_files': source_files,
            'original_file_ids': original_file_ids,
            'status': 'completed',
            'message': f'Successfully aggregated {len(all_qa_pairs)} QA pairs from {len(source_files)} files'
        }

    except Exception as e:
        logger.error(f"Error in aggregation: {str(e)}")
        return {
            'status': 'failed',
            'message': f'Error during aggregation: {str(e)}',
            'successful_files': len(successful_results) if 'successful_results' in locals() else 0,
            'failed_files': len(failed_results) if 'failed_results' in locals() else 0,
            'total_qa_pairs': len(all_qa_pairs) if 'all_qa_pairs' in locals() else 0
        }
