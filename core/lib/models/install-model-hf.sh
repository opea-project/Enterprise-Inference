
# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

deploy_from_huggingface() {
    echo "-------------------------------------------------"
    echo "|         Deploy Model from Huggingface          |"
    echo "|------------------------------------------------|"    
    hugging_face_model_deployment="true"
    read_config_file "$@"        
    prompt_for_input "$@"    
    skip_check="true"
    if [ -z "$cluster_url" ] || [ -z "$cert_file" ] || [ -z "$key_file" ] || [ -z "$keycloak_client_id" ] || [ -z "$keycloak_admin_user" ] || [ -z "$keycloak_admin_password" ] || [ -z "$hugging_face_token" ] || [ -z "$models" ]; then
        echo "Some required arguments are missing. Prompting for input..."
        prompt_for_input
    fi        
        
    read -p "Enter the Huggingface Model ID: " huggingface_model_id    
    echo "${YELLOW}NOTICE: The model deployment name will be used as the release identifier for deployment. It must be unique, meaningful, and follow Kubernetes naming conventions — lowercase letters, numbers, and hyphens only. Capital letters or special characters are not allowed. ${NC}"
    read -p "Enter Deployment Name for the Model: " huggingface_model_deployment_name
    echo "${YELLOW}NOTICE: Ensure the Tensor Parallel size value corresponds to the number of available Gaudi cards. Providing an incorrect value may result in the model being in a not ready state. ${NC}" 
    if [ "$cpu_or_gpu" = "g" ] || [ "$cpu_or_gpu" = "gaudi2" ] || [ "$cpu_or_gpu" = "gaudi3" ]; then
        read -p "Enter the Tensor Parallel size:" -r huggingface_tensor_parellel_size        
        if ! [[ "$huggingface_tensor_parellel_size" =~ ^[0-9]+$ ]]; then
            echo "Invalid input: Tensor Parallel size must be a positive integer."
            exit 1
        fi 
    fi           
    if [ -n "$huggingface_model_deployment_name" ] && [ -n "$huggingface_model_id" ]; then
        read -p "${YELLOW}NOTICE: You are about to deploy a model directly from Hugging Face, which has not been pre-validated by our team. Do you wish to continue? (y/n) ${NC}" -r user_response
        echo ""
        user_response=$(echo "$user_response" | tr '[:upper:]' '[:lower:]')        
        if [[ ! $user_response =~ ^(yes|y|Y|YES)$ ]]; then        
            echo "Deployment process has been cancelled. Exiting!!"
            exit 1
        fi
        if [ "$brownfield_deployment" == "yes" ]; then
        echo "Setting up Bastion Node..."
        setup_bastion "$@"
        INVENTORY_PATH=$brownfield_deployment_host_file
        fi
        invoke_prereq_workflows "$@"                
        execute_and_check "Deploying Inference LLM Models..." deploy_inference_llm_models_playbook "$@" \
            "Inference LLM Model is deployed successfully." \
            "Failed to deploy Inference LLM Model Exiting!." 
        echo -e "${BLUE}-------------------------------------------------------------------------------------${NC}"
        echo -e "${GREEN}|  AI LLM Model Deployment Complete!                                                |${NC}"        
        echo -e "${GREEN}|  The model is transitioning to a state ready for Inference.                       |${NC}"
        echo -e "${GREEN}|  This may take some time depending on system resources and other factors.         |${NC}"
        echo -e "${GREEN}|  Please standby...                                                                |${NC}"
        echo -e "${BLUE}--------------------------------------------------------------------------------------${NC}"
        echo ""
        echo "Accessing Deployed Models for Inference"
        echo "https://github.com/opea-project/Enterprise-Inference/blob/main/docs/accessing-deployed-models.md"
        echo ""
        echo "Please refer to this comprehensive guide for detailed instructions."          
        echo ""
    else
        echo "Required huggingface model name and model id not provided. Exiting!!"
    fi
}