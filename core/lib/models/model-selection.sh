# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

model_selection(){
    
    if [ "$list_model_menu" != "skip" ]; then
        if [ -z "$hugging_face_token" ] && [ "$deploy_llm_models" = "yes" ]; then
            read -p "Enter the token for Huggingface: " hugging_face_token
        else
            echo "Using provided Huggingface token"            
        fi
        if [ -z "$deploy_llm_models" ]; then
            read -p "Do you want to proceed with deploying Large Language Model (LLM)? (yes/no): " deploy_llm_models
            if [ "$deploy_llm_models" == "yes" ]; then
                model_name_list=$(get_model_names)    
                echo "Proceeding to deploy models: $model_name_list"
            fi
        else
            model_name_list=$(get_model_names)                       
            echo "Proceeding with the setup of Large Language Model (LLM): $deploy_llm_models"
        fi
        if [ "$deploy_llm_models" = "yes" ]; then
            if [ "$hugging_face_model_deployment" != "true" ]; then                        
                if [ -z "$models" ]; then
                    if [ "$hugging_face_model_remove_deployment" != "true" ]; then
                        if [ "$device" = "hpu" ]; then
                            # Prompt for GPU models
                            echo "Available Models for GPU Deployment:"
                            echo "1. meta-llama/Llama-3.1-8B-Instruct"
                            echo "2. meta-llama/Llama-3.1-70B-Instruct"
                            echo "3. meta-llama/Llama-3.1-405B-Instruct"
                            echo "4. meta-llama/Llama-3.3-70B-Instruct"
                            echo "5. meta-llama/Llama-4-Scout-17B-16E-Instruct"
                            echo "6. Qwen/Qwen2.5-32B-Instruct"
                            echo "7. deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
                            echo "8. deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
                            echo "9. mistralai/Mixtral-8x7B-Instruct-v0.1"
                            echo "10. mistralai/Mistral-7B-Instruct-v0.3"
                            echo "11. BAAI/bge-base-en-v1.5"
                            echo "12. BAAI/bge-reranker-base"
                            echo "13. codellama/CodeLlama-34b-Instruct-hf"
                            echo "14. tiiuae/Falcon3-7B-Instruct"
                            read -p "Enter the numbers of the GPU models you want to deploy/remove (comma-separated, e.g., 1,3,5): " models
                            # Validate input
                            IFS=',' read -ra selected <<< "$models"
                            for m in "${selected[@]}"; do
                                if ! [[ "$m" =~ ^(1|2|3|4|5|6|7|8|9|10|11|12|13|14)$ ]]; then
                                    echo "Error: Invalid model selected ($m). Exiting." >&2
                                    exit 1
                                fi
                            done
                        elif [ "$device" = "xpu" ]; then
                            # Prompt for BMG (Intel Arc Battlemage) GPU models
                            echo "Available Models for Intel Arc Battlemage (BMG) GPU Deployment:"
                            echo "31. meta-llama/Llama-3.1-8B-Instruct"
                            echo "32. mistralai/Mistral-7B-Instruct-v0.3"
                            echo "33. deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
                            echo "34. Qwen/Qwen2.5-7B-Instruct"
                            echo "35. tiiuae/Falcon3-7B-Instruct"
                            echo "36. Qwen/Qwen2.5-Coder-3B-Instruct"
                            read -p "Enter the numbers of the BMG models you want to deploy/remove (comma-separated, e.g., 31,33): " models
                            # Validate input
                            IFS=',' read -ra selected <<< "$models"
                            for m in "${selected[@]}"; do
                                if ! [[ "$m" =~ ^(31|32|33|34|35|36)$ ]]; then
                                    echo "Error: Invalid model selected ($m). Exiting." >&2
                                    exit 1
                                fi
                            done
                        else
                            # Prompt for CPU models
                            echo "Available Models for CPU Deployment:"
                            echo "21. meta-llama/Llama-3.1-8B-Instruct"
                            echo "22. meta-llama/Llama-3.2-3B-Instruct"
                            echo "23. deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
                            echo "24. deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
                            echo "25. Qwen/Qwen3-1.7B"
                            echo "26. Qwen/Qwen3-4B-Instruct-2507"
                            echo "27. Qwen/Qwen3-Coder-30B-A3B-Instruct"
                            read -p "Enter the number of the CPU model you want to deploy/remove: " cpu_model
                            # Validate input
                            if ! [[ "$cpu_model" =~ ^(21|22|23|24|25|26|27)$ ]]; then
                                echo "Error: Invalid model selected ($cpu_model). Exiting." >&2
                                exit 1
                            fi
                            models="$cpu_model"
                        fi
                    fi
                else
                    if [ "$hugging_face_model_deployment" != "true" ]; then
                        echo "Using provided models: $models"
                    fi
                fi
                
                model_names=$(get_model_names)                        
                if [ "$hugging_face_model_remove_deployment" != "true" ]; then
                    if [ -n "$model_names" ]; then
                        if [ "$hugging_face_model_deployment" != "true" ]; then                    
                            if [ "$device" = "hpu" ]; then
                                echo "Deploying/removing GPU models: $model_names"                    
                            elif [ "$device" = "xpu" ]; then
                                echo "Deploying/removing Intel Arc BMG GPU models: $model_names"
                            else
                                echo "Deploying/removing CPU models: $model_names"                    
                            fi
                        fi
                    fi
                fi            
            fi
        else
            echo "Skipping model deployment/removal."
        fi

        
    fi
    
}


get_model_names() {
    local model_names=()
    IFS=','    
    read -ra model_array <<< "$models"
    for model in "${model_array[@]}"; do
        case "$model" in
            1)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama-8b")
                ;;
            2)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama-70b")
                ;;
            3)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama3-405b")
                ;;
            4)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama-3-3-70b")
                ;;
            5)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama-4-scout-17b")
                ;;
            6)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("qwen-2-5-32b")
                ;;
            7)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("deepseek-r1-distill-qwen-32b")
                ;;
            8)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("deepseek-r1-distill-llama8b")
                ;;
            9)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("mixtral-8x-7b")
                ;;
            10)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("mistral-7b")
                ;;
            11)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("tei")
                ;;
            12)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("rerank")
                ;;
            13)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("codellama-34b")
                ;;
            14)
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("falcon3-7b")
                ;;
            21)
                if [ "$device" = "hpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: CPU model identifier provided for hpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-llama-8b")
                ;;
            22)
                if [ "$device" = "hpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: CPU model identifier provided for hpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-llama-3-2-3b")
                ;;
            23)
                if [ "$device" = "hpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: CPU model identifier provided for hpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-deepseek-r1-distill-llama8b")
                ;;
            24)
                if [ "$device" = "hpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: CPU model identifier provided for hpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-deepseek-r1-distill-qwen-32b")
                ;;
            25)
                if [ "$device" = "hpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: CPU model identifier provided for hpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-qwen3-1-7b")
                ;;
            26)
                if [ "$device" = "hpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: CPU model identifier provided for hpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-qwen3-4b")
                ;;
            27)
                if [ "$device" = "hpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: CPU model identifier provided for hpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-qwen3-coder-30b")
                ;;
            31)
                if [ "$device" = "cpu" ] || [ "$device" = "hpu" ]; then
                    echo "Error: XPU model identifier provided for cpu/hpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("bmg-llama-8b")
                ;;
            32)
                if [ "$device" = "cpu" ] || [ "$device" = "hpu" ]; then
                    echo "Error: XPU model identifier provided for cpu/hpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("bmg-mistral-7b")
                ;;
            33)
                if [ "$device" = "cpu" ] || [ "$device" = "hpu" ]; then
                    echo "Error: XPU model identifier provided for cpu/hpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("bmg-deepseek-r1-distill-llama8b")
                ;;
            34)
                if [ "$device" = "cpu" ] || [ "$device" = "hpu" ]; then
                    echo "Error: XPU model identifier provided for cpu/hpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("bmg-qwen-2-5-7b")
                ;;
            35)
                if [ "$device" = "cpu" ] || [ "$device" = "hpu" ]; then
                    echo "Error: XPU model identifier provided for cpu/hpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("bmg-falcon3-7b")
                ;;
            36)
                if [ "$device" = "cpu" ] || [ "$device" = "hpu" ]; then
                    echo "Error: XPU model identifier provided for cpu/hpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("bmg-qwen-2-5-coder-3b")
                ;;
            "llama-8b"|"llama-70b"|"codellama-34b"|"mixtral-8x-7b"|"mistral-7b"|"tei"|"tei-rerank"|"falcon3-7b"|"deepseek-r1-distill-qwen-32b"|"deepseek-r1-distill-llama8b"|"llama3-405b"|"llama-3-3-70b"|"llama-4-scout-17b"|"qwen-2-5-32b")
                if [ "$device" = "cpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: Gaudi GPU (hpu) model identifier provided for cpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("$model")
                ;;
            "cpu-llama-8b"|"cpu-deepseek-r1-distill-qwen-32b"|"cpu-deepseek-r1-distill-llama8b"|"cpu-qwen3-1-7b"|"cpu-llama-3-2-3b"|"cpu-qwen3-4b"|"cpu-qwen3-coder-30b")
                if [ "$device" = "hpu" ] || [ "$device" = "xpu" ]; then
                    echo "Error: CPU model identifier provided for hpu/xpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("$model")
                ;;
            "bmg-llama-8b"|"bmg-mistral-7b"|"bmg-deepseek-r1-distill-llama8b"|"bmg-qwen-2-5-7b"|"bmg-falcon3-7b"|"bmg-qwen-2-5-coder-3b")
                if [ "$device" = "cpu" ] || [ "$device" = "hpu" ]; then
                    echo "Error: XPU model identifier provided for cpu/hpu deployment/removal." >&2
                    exit 1
                fi
                model_names+=("$model")
                ;;
            *)
                echo "Error: Invalid model identifier: $model" >&2
                exit 1
                ;;
        esac
    done
    echo "${model_names[@]}"
}
