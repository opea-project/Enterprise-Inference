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
                        if [ "$cpu_or_gpu" = "g" ]; then
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
                        else
                            # Prompt for CPU models
                            echo "Available Models for CPU Deployment:"
                            echo "21. meta-llama/Llama-3.1-8B-Instruct"
                            echo "22. meta-llama/Llama-3.2-3B-Instruct"
                            echo "23. deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
                            echo "24. deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
                            echo "25. Qwen/Qwen3-1.7B"
                            echo "26. Qwen/Qwen3-4B-Instruct-2507"
                            read -p "Enter the number of the CPU model you want to deploy/remove: " cpu_model
                            # Validate input
                            if ! [[ "$cpu_model" =~ ^(21|22|23|24|25|26)$ ]]; then
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
                            if [ "$cpu_or_gpu" = "g" ]; then
                                echo "Deploying/removing GPU models: $model_names"                    
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
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama-8b")
                ;;
            2)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama-70b")
                ;;
            3)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama3-405b")
                ;;
            4)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama-3-3-70b")
                ;;
            5)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama-4-scout-17b")
                ;;
            6)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("qwen-2-5-32b")
                ;;
            7)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("deepseek-r1-distill-qwen-32b")
                ;;
            8)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("deepseek-r1-distill-llama8b")
                ;;
            9)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("mixtral-8x-7b")
                ;;
            10)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("mistral-7b")
                ;;
            11)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("tei")
                ;;
            12)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("rerank")
                ;;
            13)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("codellama-34b")
                ;;
            14)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("falcon3-7b")
                ;;
            21)
                if [ "$cpu_or_gpu" = "g" ]; then
                    echo "Error: CPU model identifier provided for GPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-llama-8b")
                ;;
            22)
                if [ "$cpu_or_gpu" = "g" ]; then
                    echo "Error: CPU model identifier provided for GPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-llama-3-2-3b")
                ;;
            23)
                if [ "$cpu_or_gpu" = "g" ]; then
                    echo "Error: CPU model identifier provided for GPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-deepseek-r1-distill-llama8b")
                ;;
            24)
                if [ "$cpu_or_gpu" = "g" ]; then
                    echo "Error: CPU model identifier provided for GPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-deepseek-r1-distill-qwen-32b")
                ;;
            25)
                if [ "$cpu_or_gpu" = "g" ]; then
                    echo "Error: CPU model identifier provided for GPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-qwen3-1-7b")
                ;;
            26)
                if [ "$cpu_or_gpu" = "g" ]; then
                    echo "Error: CPU model identifier provided for GPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-qwen3-4b")
                ;;
            "llama-8b"|"llama-70b"|"codellama-34b"|"mixtral-8x-7b"|"mistral-7b"|"tei"|"tei-rerank"|"falcon3-7b"|"deepseek-r1-distill-qwen-32b"|"deepseek-r1-distill-llama8b"|"llama3-405b"|"llama-3-3-70b"|"llama-4-scout-17b"|"qwen-2-5-32b")
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("$model")
                ;;
            "cpu-llama-8b"|"cpu-deepseek-r1-distill-qwen-32b"|"cpu-deepseek-r1-distill-llama8b"|"cpu-qwen3-1-7b"|"cpu-llama-3-2-3b"|"cpu-qwen3-4b")
                if [ "$cpu_or_gpu" = "g" ]; then
                    echo "Error: CPU model identifier provided for GPU deployment/removal." >&2
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
