# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


remove_model_deployed_via_huggingface(){
    echo "-------------------------------------------------"
    echo "|         Removing Model using Deployment name   |"
    echo "|------------------------------------------------|"
    hugging_face_model_remove_deployment="true"
    read_config_file "$@"       
    prompt_for_input "$@"
    skip_check="true"    
    if [ -z "$cluster_url" ] || [ -z "$cert_file" ] || [ -z "$key_file" ] || [ -z "$keycloak_client_id" ] || [ -z "$keycloak_admin_user" ] || [ -z "$keycloak_admin_password" ] || [ -z "$hugging_face_token" ] || [ -z "$models" ]; then
        echo "Some required arguments are missing. Prompting for input..."
        prompt_for_input "$@"
    fi
    read -p "${YELLOW}CAUTION: Removing the Inference LLM Model will also remove its associated services and resources, which may cause service downtime and potential data loss. This action is irreversible. Are you absolutely certain you want to proceed? (y/n) ${NC}" -r user_response    
    echo ""
    user_response=$(echo "$user_response" | tr '[:upper:]' '[:lower:]')        
    if [[ ! $user_response =~ ^(yes|y|Y|YES)$ ]]; then        
        echo "Aborting LLM Model removal process. Exiting!!"
        exit 1
    fi        
    
    read -p "Enter the deployment name of the model you wish to deprovision: " hugging_face_model_remove_name    
    if [ "$cpu_or_gpu" == "c" ]; then
        hugging_face_model_remove_name="${hugging_face_model_remove_name}-cpu"
    fi
    if [ -n "$hugging_face_model_remove_name" ]; then
        if [ "$brownfield_deployment" == "yes" ]; then
        echo "Setting up Bastion Node..."
        setup_bastion "$@"
        INVENTORY_PATH=$brownfield_deployment_host_file
        fi
        invoke_prereq_workflows "$@"                
        execute_and_check "Removing Inference LLM Models..." remove_inference_llm_models_playbook "$@" \
            "Inference LLM Model is removed successfully." \
            "Failed to remove Inference LLM Model Exiting!."
        echo "---------------------------------------------------------------------"
        echo "|     LLM Model Being Removed from Intel AI for Enterprise Inference! |"
        echo "---------------------------------------------------------------------"
        echo ""        
    else
        echo "Required huggingface model name and model id not provided. Exiting!!"
    fi
}
