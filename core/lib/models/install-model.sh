# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

deploy_inference_llm_models_playbook() {
    echo "Deploying Inference LLM Models playbook..."    
    install_true="true"
    enable_cpu_balloons="false"
    
    if [ "$cpu_or_gpu" == "c" ]; then
        cpu_playbook="true"
        gpu_playbook="false"
        gaudi_deployment="false"
        enable_cpu_balloons="true"  # Enable NRI balloons for CPU deployments
        huggingface_model_deployment_name="${huggingface_model_deployment_name}-cpu"
        if [ "$balloon_policy_cpu" == "enabled" ]; then
            echo "${GREEN}CPU deployment detected - using generic NRI balloon policy${NC}"
        fi        
    fi
    if [ "$cpu_or_gpu" == "g" ]; then
        cpu_playbook="false"
        gpu_playbook="true"
        gaudi_deployment="true"
        enable_cpu_balloons="false"
    fi
    if [ "$deploy_apisix" == "no" ]; then        
        apisix_enabled="false"
    else        
        apisix_enabled="true"
    fi
    if [ "$deploy_keycloak" == "no" ]; then
        ingress_enabled="true"        
    else
        ingress_enabled="false"        
    fi
    if [ "$deploy_observability" == "yes" ]; then
        vllm_metrics_enabled="true"        
    else
        vllm_metrics_enabled="false"        
    fi

    if [[ "$gaudi_platform" == "gaudi2" ]]; then
        gaudi_values_file=$gaudi2_values_file_path
    elif [[ "$gaudi_platform" == "gaudi3" ]]; then
        gaudi_values_file=$gaudi3_values_file_path
    fi    

    echo "Ingress based Deployment: $ingress_enabled"
    echo "APISIX Enabled: $apisix_enabled"
    echo "Keycloak Enabled: $deploy_keycloak"    
    echo "Gaudi based: $gaudi_deployment"
    echo "Model Metrics Enabled: $vllm_metrics_enabled"
    echo "CPU NRI Balloons: $enable_cpu_balloons"
    
    tags=""
    for model in $model_name_list; do
        tags+="install-$model,"
    done    
    
    if [ -n "$huggingface_model_id" ] && [[ "$tags" != *"install-$huggingface_model_id"* ]]; then
        tags+="install-$huggingface_model_deployment_name,"
    fi

    if [ "$deploy_keycloak" == "yes" ]; then
        tags+="install-keycloak-apisix,"
    fi
    if [ "$deploy_genai_gateway" == "yes" ]; then
        tags+="install-genai-gateway,"
    fi    
    
    tags=${tags%,}

    if [[ "$brownfield_deployment" == "yes" ]]; then
        echo "Brownfield deployment setup is selected..."
        INVENTORY_PATH=$brownfield_deployment_host_file
        echo $INVENTORY_PATH
        echo "Brownfield deployment setup was selected..."
    fi
        
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-inference-models.yml \
        --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} keycloak_admin_user=${keycloak_admin_user} keycloak_admin_password=${keycloak_admin_password} keycloak_client_id=${keycloak_client_id} hugging_face_token=${hugging_face_token} install_true=${install_true} model_name_list='${model_name_list//\ /,}' cpu_playbook=${cpu_playbook} gpu_playbook=${gpu_playbook} hugging_face_token_falcon3=${hugging_face_token_falcon3} deploy_keycloak=${deploy_keycloak} apisix_enabled=${apisix_enabled} ingress_enabled=${ingress_enabled} gaudi_deployment=${gaudi_deployment} huggingface_model_id=${huggingface_model_id} hugging_face_model_deployment=${hugging_face_model_deployment} huggingface_model_deployment_name=${huggingface_model_deployment_name} deploy_inference_llm_models_playbook=${deploy_inference_llm_models_playbook} huggingface_tensor_parellel_size=${huggingface_tensor_parellel_size} deploy_genai_gateway=${deploy_genai_gateway} vllm_metrics_enabled=${vllm_metrics_enabled} gaudi_values_file=${gaudi_values_file} xeon_values_file=${xeon_values_file_path} deploy_ceph=${deploy_ceph} enable_cpu_balloons=${enable_cpu_balloons} balloon_policy_cpu=${balloon_policy_cpu}" --tags "$tags" --vault-password-file "$vault_pass_file"

}

add_model() {
    read_config_file "$@"        
    prompt_for_input "$@"  
    skip_check="true"  
    if [ -z "$cluster_url" ] || [ -z "$cert_file" ] || [ -z "$key_file" ] || [ -z "$keycloak_client_id" ] || [ -z "$keycloak_admin_user" ] || [ -z "$keycloak_admin_password" ] || [ -z "$hugging_face_token" ] || [ -z "$models" ]; then
        echo "Some required arguments are missing. Prompting for input..."
        prompt_for_input "$@"
    fi    
    model_name_list=$(get_model_names)
    if [ -z "$model_name_list" ]; then
        echo "No models provided. Exiting..."
        exit 1
    fi
    echo "Deploying models: $model_name_list"
    if [ -n "$models" ]; then
        read -p "${YELLOW}NOTICE: You are initiating a model deployment. This will create the required services. Do you wish to continue? (y/n) ${NC}" -r user_response
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
    fi
}