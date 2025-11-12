# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

remove_inference_llm_models_playbook() {
    echo "Removing Inference LLM Models playbook..."        
    echo "Uninstalling the models..."      
    tags=""    
    for model in $model_name_list; do
        tags+="uninstall-$model,"
    done
    if [ -n "$hugging_face_model_remove_name" ] && [[ "$tags" != *"install-$hugging_face_model_remove_name"* ]]; then
        tags+="uninstall-$hugging_face_model_remove_name,"
    fi
    tags=${tags%,}        
    uninstall_true="true"
    if [[ "$brownfield_deployment" == "yes" ]]; then
        echo "Brownfield deployment setup is selected..."
        INVENTORY_PATH=$brownfield_deployment_host_file
    fi     
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-inference-models.yml \
        --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} keycloak_admin_user=${keycloak_admin_user} keycloak_admin_password=${keycloak_admin_password} keycloak_client_id=${keycloak_client_id} hugging_face_token=${hugging_face_token} uninstall_true=${uninstall_true} model_name_list='${model_name_list//\ /,}' hugging_face_model_remove_deployment=${hugging_face_model_remove_deployment} hugging_face_model_remove_name=${hugging_face_model_remove_name} deploy_ceph=${deploy_ceph} balloon_policy_cpu=${balloon_policy_cpu}"  --tags "$tags" --vault-password-file "$vault_pass_file" 
}

remove_model() {
    if [ "$brownfield_deployment" == "yes" ]; then
        echo "Setting up Bastion Node..."
        setup_bastion "$@"
        INVENTORY_PATH=$brownfield_deployment_host_file
    fi
    read_config_file "$@"        
    prompt_for_input "$@"
    skip_check="true"    
    if [ -z "$cluster_url" ] || [ -z "$cert_file" ] || [ -z "$key_file" ] || [ -z "$keycloak_client_id" ] || [ -z "$keycloak_admin_user" ] || [ -z "$keycloak_admin_password" ] || [ -z "$hugging_face_token" ] || [ -z "$models" ]; then
        echo "Some required arguments are missing. Prompting for input..."
        prompt_for_input
    fi    
    model_name_list=$(get_model_names)
    if [ -z "$model_name_list" ]; then
        echo "No models provided. Exiting..."
        exit 1
    fi
    echo "Removing models: $model_name_list"
    if [ -n "$models" ]; then
        read -p "${YELLOW}CAUTION: Removing the Inference LLM Model will also remove its associated services and resources, which may cause service downtime and potential data loss. This action is irreversible. Are you absolutely certain you want to proceed? (y/n)${NC} " -r user_response
        echo ""
        user_response=$(echo "$user_response" | tr '[:upper:]' '[:lower:]')        
        if [[ ! $user_response =~ ^(yes|y|Y|YES)$ ]]; then                
            echo "Aborting LLM Model removal process. Exiting!!"
            exit 1
        fi
        invoke_prereq_workflows "$@"       
        execute_and_check "Removing Inference LLM Models..." remove_inference_llm_models_playbook "$@" \
            "Inference LLM Model is removed successfully." \
            "Failed to remove Inference LLM Model Exiting!."
        echo -e "${BLUE}------------------------------------------------------------------------------${NC}"
        echo -e "${GREEN}|  AI LLM Model is being removed from Intel AI for Enterprise Inference!       |${NC}"
        echo -e "${GREEN}|  This may take some time depending on system resources and other factors.  |${NC}"
        echo -e "${GREEN}|  Please standby...                                                         |${NC}"
        echo -e "${BLUE}------------------------------------------------------------------------------${NC}"
    fi
}