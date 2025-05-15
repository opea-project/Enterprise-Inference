#!/bin/bash

# Colors
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
BLUE=$(tput setaf 4)
NC=$(tput sgr0)  # Reset color


# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
# Permission is granted for recipient to internally use and modify this software for purposes of benchmarking and testing on Intel architectures. 
# This software is provided "AS IS" possibly with faults, bugs or errors; it is not intended for production use, and recipient uses this design at their own risk with no liability to Intel.
# Intel disclaims all warranties, express or implied, including warranties of merchantability, fitness for a particular purpose, and non-infringement. 
# Recipient agrees that any feedback it provides to Intel about this software is licensed to Intel for any purpose worldwide. No permission is granted to use Intel’s trademarks.
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the code.


#############################################################################
# Usage Documentation
#############################################################################

# Inference as a Service Deployment Automation Script

# This script automates the setup, reset, and update of a Kubernetes cluster with Inference as a Service using Ansible playbooks. 
# It includes functions for setting up a virtual environment, installing Kubernetes, deploying various components 
# (e.g., Habana AI Operator, Ingress NGINX Controller, Keycloak), and managing models and worker nodes.

# Prerequisites


# 1. Gaudi Driver update, Firmware update and Reboot
# 2. ida/kray/inventory/mycluster/hosts.yaml file should be updated with the correct IP addresses of the nodes.
# 3. This automation need to be invoked from a bastion host.

# Usage

# Running the Script

# To run the script, execute the following command in your terminal:

# ./inference-stack-deploy.sh [OPTIONS]

# Options

# The script accepts the following command-line options:

# --cluster-url <URL>: The cluster URL (FQDN).
# --cert-file <path>: The full path to the certificate file.
# --key-file <path>: The full path to the key file.
# --keycloak-client-id <id>: The Keycloak client ID.
# --keycloak-admin-user <username>: The Keycloak admin username.
# --keycloak-admin-password <password>: The Keycloak admin password.
# --hugging-face-token <token>: The token for Huggingface.
# --models <models>: The models to deploy (comma-separated list of model numbers or names).
# --cpu-or-gpu <c/g>: Specify whether to run on CPU or GPU.

# Main Menu

# When you run the script, you will be presented with a main menu with the following options:

# 1. Setup k8s Cluster with Inference as Service: Perform a fresh installation of the Kubernetes cluster with Inference as a Service.
# 2. K8sPurgeCluster: Reset the existing Kubernetes cluster.
# 3. Update Existing Cluster: Update the existing Kubernetes cluster.

# Fresh Installation

# If you choose to perform a fresh installation, the script will prompt you for the necessary inputs and proceed with the following steps:

# 1. Prompt for Input: Collects the required inputs from the user.
# 2. Setup Initial Environment: Sets up the virtual environment and installs necessary dependencies.
# 3. Install Kubernetes: Installs Kubernetes and sets up the kubeconfig for the user.
# 4. Deploy Components: Deploys the selected components (Habana AI Operator, Ingress NGINX Controller, Keycloak, and models).

# Reset Cluster

# If you choose to reset the cluster, the script will:

# 1. Prompt for Confirmation: Asks for confirmation before proceeding with the reset.
# 2. Setup Initial Environment: Sets up the virtual environment and installs necessary dependencies.
# 3. Run Reset Playbook: Executes the Ansible playbook to reset the cluster.

# Update Existing Cluster

# If you choose to update the existing cluster, the script will present you with the following options:

# 1. Manage Worker Nodes: Add or remove worker nodes.
# 2. Manage Models: Add or remove models.

# Example
# To perform a fresh installation with specific parameters, you can run:
# ./inference-stack-deploy.sh --cluster-url "https://example.com" --cert-file "/path/to/cert.pem" --key-file "/path/to/key.pem" --keycloak-client-id "my-client-id" --keycloak-admin-user "user" --keycloak-admin-password "password" --hugging-face-token "token" --models "1,3,5" --cpu-or-gpu "g"

##############################################################################

#echo "All arguments: $@"

function usage() {
    cat <<EOF
##############################################################################

--------------------------------------------
Inference as a Service Deployment Automation
--------------------------------------------

Usage: ./inference-stack-deploy.sh [OPTIONS]

Automates Kubernetes cluster setup and management for Inference as a Service.

Options:
  --cluster-url <URL>            Cluster URL (FQDN).
  --cert-file <path>             Path to certificate file.
  --key-file <path>              Path to key file.
  --keycloak-client-id <id>      Keycloak client ID.
  --keycloak-admin-user <user>   Keycloak admin username.
  --keycloak-admin-password <pw> Keycloak admin password.
  --hugging-face-token <token>   Huggingface token.
  --models <models>              Models to deploy (comma-separated).
  --cpu-or-gpu <c/g>             Run on CPU (c) or GPU (g).

Examples:
  Setup cluster: ./inference-stack-deploy.sh --cluster-url "https://example.com" --cert-file "/path/cert.pem" --key-file "/path/key.pem" --keycloak-client-id "client-id" --keycloak-admin-user "user" --keycloak-admin-password "password" --hugging-face-token "token" --models "1,3,5" --cpu-or-gpu "g"

###############################################################################  
EOF
}


HOMEDIR="$(pwd)"
KUBESPRAYDIR="$(dirname "$(realpath "$0")")/kubespray"
# Set the virtual environment directory to the script location
VENVDIR="$(dirname "$(realpath "$0")")/kubespray225-venv"
INVENTORY_PATH="${KUBESPRAYDIR}/inventory/mycluster/hosts.yaml"
# Set the default values for the parameters
cluster_url=""
cert_file=""
key_file=""
keycloak_client_id=""
keycloak_admin_user=""
keycloak_admin_password=""
hugging_face_token=""
models=""
model_name_list=""
cpu_or_gpu=""
deploy_kubernetes_fresh=""
deploy_habana_ai_operator=""
deploy_ingress_controller=""
deploy_keycloak_and_apisix=""
deploy_llm_models=""
list_model_menu=""
apisix_enabled=""
ingress_enabled=""
deploy_keycloak=""
deploy_apisix=""
delete_pv_on_purge=""
prereq_executed=0
hugging_face_model_deployment=""
huggingface_model_id=""
huggingface_model_deployment_name=""
hugging_face_model_remove_deployment=""
hugging_face_model_remove_name=""
huggingface_tensor_parellel_size=""




read_config_file() {
    local config_file="$HOMEDIR/inference-config.cfg"
    if [ -f "$config_file" ]; then
        echo "Configuration file found, setting vars!"
        echo "---------------------------------------"
        while IFS='=' read -r key value || [ -n "$key" ]; do
            # Trim leading/trailing whitespace
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)
            # Set the variable using a temporary file
            if [[ "$value" == "on" ]]; then
                value="yes"
            elif [[ "$value" == "off" ]]; then
                value="no"
            fi
            printf "%s=%s\n" "$key" "$value" >> temp_env_vars                        
        done < "$config_file"        
        # Load the environment variables from the temporary file
        source temp_env_vars        
        rm temp_env_vars        
        case "$cpu_or_gpu" in
            "c" | "cpu")
                cpu_or_gpu="c"
                deploy_habana_ai_operator="no"
                ;;
            "g" | "gpu")
                cpu_or_gpu="g"
                deploy_habana_ai_operator="yes"
                ;;
            *)
                echo "Invalid value for cpu_or_gpu. It should be either 'c' or 'cpu' for CPU, or 'g' or 'gpu' for GPU."
                exit 1
                ;;
        esac
        case "$deploy_keycloak_apisix" in
            "no")
                deploy_apisix="no"
                deploy_keycloak="no"                
                ;;
            "yes")
                deploy_apisix="yes"
                deploy_keycloak="yes"                
                ;;
            *)
                echo "Incorrect value for deploy_keycloak_apisix"
                exit 1
                ;;
        esac
    else
        echo "Configuration file not found. Using default values or prompting for input."
    fi    
}

setup_initial_env() {\
    echo "Setting up the Initial Environment..."    
    if [ ! -d "$KUBESPRAYDIR" ]; then
        git clone https://github.com/kubernetes-sigs/kubespray.git $KUBESPRAYDIR
        cd $KUBESPRAYDIR
        git checkout v2.25.0
    else
        echo "Kubespray directory already exists, skipping clone."
        cd $KUBESPRAYDIR
    fi
     # Install pip if not present
    if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
        echo "pip not found, attempting to install..."
        curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
        python3 get-pip.py --user
        rm get-pip.py
    elif command -v pip3 &> /dev/null; then
        echo "pip3 is already installed."        
    else
        echo "pip is already installed."
        
    fi
    # Create and activate virtual environment within Kubespray directory
    VENVDIR="$KUBESPRAYDIR/venv"
    if [ ! -d "$VENVDIR" ]; then
        python3 -m pip install --upgrade pip
        python3 -m pip install virtualenv
        python3 -m virtualenv $VENVDIR
        echo "Virtual environment created within Kubespray directory."
    else
        echo "Virtual environment already exists within Kubespray directory, skipping creation."
    fi
    source $VENVDIR/bin/activate
    echo "Attempting to activate the virtual environment..."
    # Check if the virtual environment is activated
    if [ -z "$VIRTUAL_ENV" ]; then
        echo "Failed to activate the virtual environment."
        return 1
    else
        echo "Virtual environment activated successfully. Path: $VIRTUAL_ENV"
    fi
    export PIP_BREAK_SYSTEM_PACKAGES=1
    # Install Kubespray requirements
    pip install -U -r requirements.txt
    echo "Kubespray requirements installed."    
    # Move deploy files to Kubespray directory
    cp -r "$HOMEDIR"/deploy-* $KUBESPRAYDIR/
    cp -r "$HOMEDIR"/helm-charts $KUBESPRAYDIR/       
    cp -r "$HOMEDIR"/scripts $KUBESPRAYDIR/       
    cp -r "$KUBESPRAYDIR"/inventory/sample/ "$KUBESPRAYDIR"/inventory/mycluster
    cp  "$HOMEDIR"/inventory/hosts.yaml $KUBESPRAYDIR/inventory/mycluster/
    cp "$HOMEDIR"/inventory/addons.yml $KUBESPRAYDIR/inventory/mycluster/group_vars/k8s_cluster/addons.yml
    
    # Copy playbooks directory
    cp "$HOMEDIR"/playbooks/* "$KUBESPRAYDIR"/playbooks/    
    echo "Additional files and directories copied to Kubespray directory."
    ansible-galaxy collection install community.kubernetes    
}


invoke_prereq_workflows() {
    if [ $prereq_executed -eq 0 ]; then
        read_config_file
        if [ -z "$cluster_url" ] || [ -z "$cert_file" ] || [ -z "$key_file" ] || [ -z "$keycloak_client_id" ] || [ -z "$keycloak_admin_user" ] || [ -z "$keycloak_admin_password" ]; then
            echo "Some required arguments are missing. Prompting for input..."
            prompt_for_input
        fi
        setup_initial_env
        # Set the flag to 1 (executed)
        prereq_executed=1
    else
        echo "Prerequisites have already been executed. Skipping..."
    fi
}

check_cluster_state() {
    echo "Checking the state of the Kubernetes cluster..."
    ansible-playbook -i inventory/mycluster/hosts.yaml --become --become-user=root upgrade-cluster.yml --check
    # Check the exit status of the Ansible playbook command
    if [ $? -eq 0 ]; then
        echo "Kubernetes cluster state check completed successfully."
    else
        echo "Kubernetes cluster state check indicates potential issues."
        return 1 # Return a non-zero value to indicate potential issues
    fi
}

run_reset_playbook() {
    echo "Running the Ansible playbook to reset the cluster..."  
    delete_pv_on_purge="yes"      
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-keycloak-controller.yml --extra-vars "delete_pv_on_purge=${delete_pv_on_purge}"
    ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root reset.yml -e "confirm_reset=yes reset_nodes=false"  
    # Check the exit status of the Ansible playbook command
    if [ $? -eq 0 ]; then
        echo "Cluster reset playbook execution completed successfully."
    else
        echo "Cluster reset playbook execution failed."
        return 1 # Return a non-zero value to indicate failure
    fi
}

reset_cluster() {
    echo "-------------------------------------------------------"
    echo "|     Purge Cluster! Inference as Service!             |"
    echo "-------------------------------------------------------"
    echo "${YELLOW}NOTICE: You are initiating a reset of the existing Inference Service Cluster."
    echo "This action will erase all current configurations, services and resources. Potentially causing service interruptions and data loss. This operation cannot be undone. ${NC}"
    read -p "Are you sure you want to proceed? (yes/no): " confirm_reset            
    if [[ "$confirm_reset" =~ ^(yes|y|Y)$ ]]; then
        echo "Resetting the existing Inference as service cluster..."
        setup_initial_env
        run_reset_playbook
        # Check if the playbook execution was successful
        if [ $? -eq 0 ]; then
            echo "Cluster reset completed."
            echo -e "${BLUE}-----------------------------------------------------------------${NC}"
            echo -e "${GREEN}|  Cluster Purge Initiated!                                       |${NC}"
            echo -e "${GREEN}|  Preparing to transition the system.                            |${NC}"
            echo -e "${GREEN}|  This process may take some time depending on system resources  |${NC}"
            echo -e "${GREEN}|  and other factors. Please standby...                           |${NC}"
            echo -e "${BLUE}------------------------------------------------------------------${NC}"
            echo ""
        else
            echo "Cluster reset failed."
        fi
    else
        echo "Reset operation cancelled."
        return
    fi
}

run_fresh_install_playbook() {
    echo "Running the cluster.yml playbook to set up the Kubernetes cluster..."
    ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root cluster.yml
}

run_kube_conf_copy_playbook() {
    echo "Running the setup-user-kubeconfig.yml playbook to set up kubeconfig for the user..."
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/setup-user-kubeconfig.yml
}

run_k8s_cluster_wait() {
    echo "Waiting for Kubernetes control plane to become ready..."
    ansible -i "${INVENTORY_PATH}" kube_control_plane -m wait_for -a "port=6443 timeout=600" --become --become-user=root   
    return $?
}

run_deploy_habana_ai_operator_playbook() {
    echo "Running the deploy-habana-ai-operator.yml playbook to deploy the habana-ai-operator..."
    ansible-galaxy collection install community.kubernetes
    ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root deploy-habana-ai-operator.yml
    if [ $? -eq 0 ]; then
        echo "The deploy-habana-ai-operator.yml playbook ran successfully."
    else
        echo "The deploy-habana-ai-operator.yml playbook encountered an error."
        exit 1
    fi
}

run_ingress_nginx_playbook() {
    echo "Deploying the Ingress NGINX Controller..."
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-ingress-controller.yml --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file}" 
}

install_ansible_collection() {
    echo "Installing community.general collection..."
    ansible-galaxy collection install community.general
}

run_keycloak_playbook() {
    echo "Deploying Keycloak using Ansible playbook..."
    install_ansible_collection    
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-keycloak-controller.yml
}

execute_and_check() {
    local description=$1
    local command=$2
    local success_message=$3
    local failure_message=$4
    echo "$description"
    $command
    if [ $? -eq 0 ]; then
        echo "$success_message"
    else
        echo "$failure_message"
        exit 1
    fi
}

create_keycloak_tls_secret_playbook() {
    echo "Deploying Keycloak TLS secret playbook..."    
    echo "************************************"        
    
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-keycloak-tls-cert.yml \
        --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} keycloak_admin_user=${keycloak_admin_user} keycloak_admin_password=${keycloak_admin_password} keycloak_client_id=${keycloak_client_id} hugging_face_token=${hugging_face_token} model_name_list='${model_name_list//\ /,}'  deploy_keycloak=${deploy_keycloak}  deploy_apisix=${deploy_apisix} "
}

deploy_inference_llm_models_playbook() {
    echo "Deploying Inference LLM Models playbook..."    
    install_true="true"        
    if [ "$cpu_or_gpu" == "c" ]; then
        cpu_playbook="true"
        gpu_playbook="false"
        gaudi_deployment="false"
        huggingface_model_deployment_name="${huggingface_model_deployment_name}-cpu"
    else
        cpu_playbook="false"
        gpu_playbook="true"
        gaudi_deployment="true"
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
    
    echo "Ingress based Deployment: $ingress_enabled"
    echo "APISIX Enabled: $apisix_enabled"
    echo "Keycloak Enabled: $deploy_keycloak"    
    echo "Gaudi based: $gaudi_deployment"
    echo "Model Metrics Enabled: $vllm_metrics_enabled"
    
    tags=""    
    for model in $model_name_list; do
        tags+="install-$model,"
    done    
    
    if [ -n "$huggingface_model_id" ] && [[ "$tags" != *"install-$huggingface_model_id"* ]]; then
        tags+="install-$huggingface_model_deployment_name,"
    fi
    
    tags=${tags%,}
        
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-inference-models.yml \
        --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} keycloak_admin_user=${keycloak_admin_user} keycloak_admin_password=${keycloak_admin_password} keycloak_client_id=${keycloak_client_id} hugging_face_token=${hugging_face_token} install_true=${install_true} model_name_list='${model_name_list//\ /,}' cpu_playbook=${cpu_playbook} gpu_playbook=${gpu_playbook} hugging_face_token_falcon3=${hugging_face_token_falcon3} deploy_keycloak=${deploy_keycloak} apisix_enabled=${apisix_enabled} ingress_enabled=${ingress_enabled} gaudi_deployment=${gaudi_deployment} huggingface_model_id=${huggingface_model_id} hugging_face_model_deployment=${hugging_face_model_deployment} huggingface_model_deployment_name=${huggingface_model_deployment_name} deploy_inference_llm_models_playbook=${deploy_inference_llm_models_playbook} huggingface_tensor_parellel_size=${huggingface_tensor_parellel_size} vllm_metrics_enabled=${vllm_metrics_enabled} " --tags "$tags"
}

deploy_observability_playbook() {
    tags=""
    if [ "${deploy_observability}" = "yes" ]; then
        tags+="deploy_observability,"
    fi
    if [ "${deploy_logging}" = "yes" ]; then
        tags+="deploy_logging,"
    fi
    tags="${tags%,}"            
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-observability.yml --become --become-user=root --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} deploy_observability=${deploy_observability} deploy_logging=${deploy_logging}" --tags "$tags"
    
}

deploy_cluster_config_playbook() {    
    if [ "${deploy_observability}" = "on" ]; then
        tags="deploy_cluster_dashboard"
    else
        tags=""        
    fi
    
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-cluster-config.yml --become --become-user=root --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file}" --tags "$tags"
}


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
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-inference-models.yml \
        --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} keycloak_admin_user=${keycloak_admin_user} keycloak_admin_password=${keycloak_admin_password} keycloak_client_id=${keycloak_client_id} hugging_face_token=${hugging_face_token} uninstall_true=${uninstall_true} model_name_list='${model_name_list//\ /,}' hugging_face_model_remove_deployment=${hugging_face_model_remove_deployment} hugging_face_model_remove_name=${hugging_face_model_remove_name}" --tags "$tags"
}

add_inference_nodes_playbook() {    
    echo "Add Inference LLM Nodes playbook..."        
    read -p "Enter the name of the worker node to be added (as defined in hosts.yml): " worker_node_name    
    if [ -z "$worker_node_name" ]; then
        echo "Error: No worker node names provided."
        return 1
    fi    
    if ! [[ "$worker_node_name" =~ ^[a-zA-Z0-9,-]+$ ]]; then
        echo "Error: Invalid characters in worker node names. Only alphanumeric characters, commas, and hyphens are allowed."
        return 1
    fi
    invoke_prereq_workflows     

    ansible-playbook -i "${INVENTORY_PATH}" playbooks/cluster.yml --become --become-user=root
    
}

remove_inference_nodes_playbook() {
    echo "Remove Inference LLM Nodes playbook..."
    # Prompt the user for the worker node names to be removed
    read -p "Enter the names of the worker nodes to be removed (comma-separated, as defined in hosts.yml): " worker_nodes_to_remove            
    if [ -z "$worker_nodes_to_remove" ]; then
        echo "Error: No worker node names provided."
        return 1
    fi
    # Check if the input contains invalid characters
    if ! [[ "$worker_nodes_to_remove" =~ ^[a-zA-Z0-9,-]+$ ]]; then
        echo "Error: Invalid characters in worker node names. Only alphanumeric characters, commas, and hyphens are allowed."
        return 1
    fi
    invoke_prereq_workflows
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/remove_node.yml --become --become-user=root -e node="$worker_nodes_to_remove" -e allow_ungraceful_removal=true
}

list_inference_llm_models_playbook() {
    echo "Listing installed Inference LLM Models playbook..."
    # Read existing parameters
    # Execute the Ansible playbook with all parameters
    echo $model_name_list
    echo "Listing the models..."
    list_model_true="true"       
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-inference-models.yml \
        --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} keycloak_admin_user=${keycloak_admin_user} keycloak_admin_password=${keycloak_admin_password} keycloak_client_id=${keycloak_client_id} hugging_face_token=${hugging_face_token} uninstall_true=${uninstall_true} list_model_true='${list_model_true//\ /,}'"
}

prompt_for_input() {   
    if [ -z "$deploy_kubernetes_fresh" ]; then
        read -p "Do you want to proceed with deploying fresh Kubernetes cluster setup? (yes/no): " deploy_kubernetes_fresh
    else
        echo "Proceeding with the setup of Fresh Kubernetes cluster: $deploy_kubernetes_fresh"
    fi
    if [ -z "$deploy_habana_ai_operator" ]; then
        read -p "Do you want to proceed with deploying Habana AI Operator? (yes/no): " deploy_habana_ai_operator
    else
        echo "Proceeding with the setup of Habana AI Operator: $deploy_habana_ai_operator"
    fi
    if [ -z "$deploy_ingress_controller" ]; then
        read -p "Do you want to proceed with deploying Ingress NGINX Controller? (yes/no): " deploy_ingress_controller
    else
        echo "Proceeding with the setup of Ingress Controller: $deploy_ingress_controller"
    fi
    if [ -z "$deploy_keycloak" ]; then
        read -p "Do you want to proceed with deploying Keycloak & APISIX? (yes/no): " deploy_keycloak
        
    else
        echo "Proceeding with the setup of Keycloak : $deploy_keycloak"
    fi
    if [ -z "$deploy_apisix" ]; then
        read -p "Do you want to proceed with deploying Keycloak & APISIX? (yes/no): " deploy_apisix
        
    else
        echo "Proceeding with the setup of Apisix: $deploy_apisix"
    fi
    
    if [ -z "$deploy_observability" ]; then
        read -p "Do you want to proceed with deploying Observability? (yes/no): " deploy_observability
    else
        echo "Proceeding with the setup of Observability: $deploy_observability"
    fi

    model_selection "$@"

    echo "----- Input -----"
    if [ -z "$cluster_url" ]; then
        read -p "Enter the CLUSTER URL (FQDN): " cluster_url
    else
        echo "Using provided CLUSTER URL: $cluster_url"
    fi
    if [ -z "$cert_file" ]; then
        read -p "Enter the full path to the certificate file: " cert_file
    else
        echo "Using provided certificate file: $cert_file"
    fi
    if [ -z "$key_file" ]; then
        read -p "Enter the full path to the key file: " key_file
    else
        echo "Using provided key file: $key_file"
    fi
    if [ -z "$keycloak_client_id" ]; then
        read -p "Enter the keycloak client id: " keycloak_client_id
    else
        echo "Using provided keycloak client id: $keycloak_client_id"
    fi
    if [ -z "$keycloak_admin_user" ]; then
        read -p "Enter the Keycloak admin username: " keycloak_admin_user
    else
        echo "Using provided Keycloak admin username: $keycloak_admin_user"
    fi
    if [ -z "$keycloak_admin_password" ]; then
        read -sp "Enter the Keycloak admin password: " keycloak_admin_password
        echo
    else
        echo "Using provided Keycloak admin password"
    fi
    
    if [[ -z "$cpu_or_gpu" ]]; then
        read -p "Do you want to run on CPU or GPU? (c/g): " cpu_or_gpu
        case "$cpu_or_gpu" in
            c|C)
                cpu_or_gpu="c"
                echo "Running on CPU"
                ;;
            g|G)
                cpu_or_gpu="g"
                echo "Running on GPU"
                ;;
            *)
                echo "Invalid option. Defaulting to CPU."
                cpu_or_gpu="c"
                ;;
        esac
    else
        echo "cpu_or_gpu is already set to $cpu_or_gpu"
    fi
    
}

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
                            echo "Available GPU models:"
                            echo "1. llama-8b"
                            echo "2. llama-70b"
                            echo "3. codellama-34b"
                            echo "4. mixtral-8x-7b"
                            echo "5. mistral-7b"
                            echo "6. tei"
                            echo "7. tei-rerank"
                            echo "8. falcon3-7b"
                            echo "9. deepseek-r1-distill-qwen-32b"
                            echo "10. deepseek-r1-distill-llama8b"
                            echo "11. llama3-405b"
                            read -p "Enter the numbers of the GPU models you want to deploy/remove (comma-separated, e.g., 1,3,5): " models
                        else
                            # Prompt for CPU models
                            echo "Available CPU models:"
                            echo "21. cpu-llama-8b"
                            echo "22. cpu-deepseek-r1-distill-qwen-32b"
                            echo "23. cpu-deepseek-r1-distill-llama8b"
                            read -p "Enter the number of the CPU model you want to deploy/remove: " cpu_model
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

parse_arguments() {
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --cluster-url) cluster_url="$2"; shift ;;
            --cert-file) cert_file="$2"; shift ;;
            --key-file) key_file="$2"; shift ;;
            --keycloak-client-id) keycloak_client_id="$2"; shift ;;
            --keycloak-admin-user) keycloak_admin_user="$2"; shift ;;
            --keycloak-admin-password) keycloak_admin_password="$2"; shift ;;
            --hugging-face-token) hugging_face_token="$2"; shift ;;
            --models) models="$2"; shift ;;
            --cpu-or-gpu) cpu_or_gpu="$2"; shift ;;
            -h|--help) usage; exit 0 ;;
            *) echo "Unknown parameter passed: $1"; exit 1 ;;
        esac
        shift
    done
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
                model_names+=("codellama-34b")
                ;;
            4)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("mixtral-8x-7b")
                ;;
            5)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("mistral-7b")
                ;;
            6)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("tei")
                ;;
            7)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("rerank")
                ;;
            8)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("falcon3-7b")
                ;;
            9)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("deepseek-r1-distill-qwen-32b")
                ;;
            10)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("deepseek-r1-distill-llama8b")
                ;;
            11)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama3-405b")
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
                model_names+=("cpu-deepseek-r1-distill-qwen-32b")
                ;;
            23)
                if [ "$cpu_or_gpu" = "g" ]; then
                    echo "Error: CPU model identifier provided for GPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("cpu-deepseek-r1-distill-llama8b")
                ;;
            "llama-8b"|"llama-70b"|"codellama-34b"|"mixtral-8x-7b"|"mistral-7b"|"tei"|"tei-rerank"|"falcon3-7b"|"deepseek-r1-distill-qwen-32b"|"deepseek-r1-distill-llama8b"|"llama3-405b")
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("$model")
                ;;
            "cpu-llama-8b"|"cpu-deepseek-r1-distill-qwen-32b"|"cpu-deepseek-r1-distill-llama8b")
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


install_kubernetes() {
    echo "Starting Kubernetes installation..."
    execute_and_check "Checking if the K8 is installed ..." run_fresh_install_playbook \
        "Kubernetes is installed." \
        "Kubernetes Installation failed. Exiting."
    execute_and_check "Checking if the Kubernetes control plane is ready..." run_k8s_cluster_wait \
        "Kubernetes control plane is ready." \
        "Kubernetes control plane did not become ready in time. Exiting."
    execute_and_check "Setting up kubeconfig for the user..." run_kube_conf_copy_playbook \
        "Kubeconfig is set up." \
        "Failed to set up kubeconfig for the user. Exiting."
}

fresh_installation() {    
    read_config_file        
    if [[ "$deploy_kubernetes_fresh" == "no" && "$deploy_habana_ai_operator" == "no" && "$deploy_ingress_controller" == "no" && "$deploy_keycloak" == "no" && "$deploy_apisix" == "no" && "$deploy_llm_models" == "no" && "$deploy_observability" == "no" ]]; then
        echo "No installation or deployment steps selected. Skipping setup_initial_env..."
        echo "-------------------------------------------------------"
        echo "|     Deployment Skipped for Inference as Service!    |"
        echo "-------------------------------------------------------"
    else
        prompt_for_input                        
        read -p "${YELLOW}ATTENTION: Ensure that the nodes do not contain existing workloads. If necessary, please purge any previous cluster configurations before initiating a fresh installation to avoid an inappropriate cluster state. Proceeding without this precaution could lead to service disruptions or data loss. Do you wish to continue with the setup? (yes/no) ${NC}" -r proceed_with_installation        
        
        if [[ "$proceed_with_installation" =~ ^([yY][eE][sS]|[yY])+$ ]]; then      
            echo "Starting fresh installation of Inference as a Service Cluster..."    
            setup_initial_env        
            if [[ "$deploy_kubernetes_fresh" == "yes" ]]; then
                install_kubernetes "$@"
            else
                echo "Skipping Kubernetes installation..."
            fi
            execute_and_check "Deploying Cluster Configuration Playbook..." deploy_cluster_config_playbook \
                  "Cluster Configuration Playbook is deployed successfully." \
                  "Failed to deploy Cluster Configuration Playbook. Exiting."
            if [[ "$deploy_habana_ai_operator" == "yes" ]]; then
                execute_and_check "Deploying habana-ai-operator..." run_deploy_habana_ai_operator_playbook "Habana AI Operator is deployed." \
                    "Failed to deploy Habana AI Operator. Exiting."
            else
                echo "Skipping Habana AI Operator installation..."
            fi
            if [[ "$deploy_ingress_controller" == "yes" ]]; then
                execute_and_check "Deploying Ingress NGINX Controller..." run_ingress_nginx_playbook \
                    "Ingress NGINX Controller is deployed successfully." \
                    "Failed to deploy Ingress NGINX Controller. Exiting."
            else
                echo "Skipping Ingress NGINX Controller deployment..."
            fi            
            
            if [[ "$deploy_keycloak" == "yes" || "$deploy_apisix" == "yes" ]]; then        
                execute_and_check "Deploying Keycloak..." run_keycloak_playbook \
                    "Keycloak is deployed successfully." \
                    "Failed to deploy Keycloak. Exiting."
                execute_and_check "Deploying Keycloak TLS secret..." create_keycloak_tls_secret_playbook "$@" \
                    "Keycloak TLS secret is deployed successfully." \
                    "Failed to deploy Keycloak TLS secret. Exiting."
            else
                echo "Skipping Keycloak deployment..."
            fi
            
            if [[ "$deploy_observability" == "yes" ]]; then
                echo "Deploying observability..."
                execute_and_check "Deploying Observability..." deploy_observability_playbook "$@" \
                    "Observability is deployed successfully." \
                    "Failed to deploy Observability. Exiting!."
            else
                echo "Skipping Observability deployment..."
            fi
            
            
            if [[ "$deploy_llm_models" == "yes" ]]; then
                model_name_list=$(get_model_names)                
                if [ -z "$model_name_list" ]; then
                    echo "No models provided. Exiting..."
                    exit 1
                    fi
                execute_and_check "Deploying Inference LLM Models..." deploy_inference_llm_models_playbook "$@" \
                    "Inference LLM Model is deployed successfully." \
                    "Failed to deploy Inference LLM Model Exiting!."
            else
                echo "Skipping LLM Model deployment..."
            fi
            
            
            
            if [ "$deploy_llm_models" == "yes" ]; then
            echo -e "${BLUE}-------------------------------------------------------------------------------------${NC}"
            echo -e "${GREEN}|  AI LLM Model Deployment Complete!                                                |${NC}"
            echo -e "${GREEN}|  The model is transitioning to a state ready for Inference.                       |${NC}"
            echo -e "${GREEN}|  This may take some time depending on system resources and other factors.         |${NC}"
            echo -e "${GREEN}|  Please standby...                                                                |${NC}"
            echo -e "${BLUE}--------------------------------------------------------------------------------------${NC}"
            echo ""
            echo "Accessing Deployed Models for Inference"
            echo "https://github.com/intel-innersource/applications.ai.erag.infra-automation/tree/main/ida#accessing-deployed-models-for-inference"
            echo ""
            echo "Please refer to this comprehensive guide for detailed instructions." 
            echo "" 
            else
            echo -e "${BLUE}-------------------------------------------------------------------------------------${NC}"
            echo -e "${GREEN}|  AI Inference Deployment Complete!                                                |${NC}"
            echo -e "${GREEN}|  Resources are transitioning to a state ready for Inference.                      |${NC}"
            echo -e "${GREEN}|  This may take some time depending on system resources and other factors.         |${NC}"
            echo -e "${GREEN}|  Please standby...                                                                |${NC}"
            echo -e "${BLUE}--------------------------------------------------------------------------------------${NC}"
            echo ""
            echo "Accessing Deployed Resources for Inference"
            echo "https://github.com/intel-innersource/applications.ai.erag.infra-automation/tree/main/ida#accessing-deployed-models-for-inference"
            echo ""
            echo "Please refer to this comprehensive guide for detailed instructions." 
            echo "" 
            fi                     
        else
            echo "-------------------------------------------------------"
            echo "|     Deployment Skipped for Inference as Service!    |"
            echo "-------------------------------------------------------"
        fi
    fi
}

update_gaudi_drivers() {
    read -p "WARNING: Updating Gaudi drivers may cause system downtime. Do you want to proceed? (yes/no) " -r
    echo
    if [[ $REPLY =~ ^(yes|y|Y)$ ]]; then
        echo "Initiating Gaudi driver update process..."
        execute_and_check "Deploying Drivers..." update_drivers \
                        "Gaudi Driver updated successfully. Please reboot the machine for changes to take effect." \
                        "Failed to update Gaudi driver. Exiting."
    else
        echo "Gaudi driver update cancelled."
    fi
}
update_gaudi_firmware() {
    read -p "WARNING: Updating Gaudi firmware may cause system downtime. Do you want to proceed? (yes/no) " -r
    echo
    if [[ $REPLY =~ ^(yes|y|Y)$ ]]; then
        echo "Initiating Gaudi firmware update process..."
        execute_and_check "Deploying Firmware..." update_firmware \
                        "Gaudi Firmware updated successfully. Please reboot the machine for changes to take effect." \
                        "Failed to update Gaudi Firmware. Exiting."
    else
        echo "Gaudi firmware update cancelled."
    fi
}
update_gaudi_driver_and_firmware_both() {
    read -p "WARNING: Updating Gaudi drivers and firmware may cause system downtime. Do you want to proceed? (yes/no) " -r
    echo
    if [[ $REPLY =~ ^(yes|y|Y)$ ]]; then
        echo "Initiating Gaudi driver and firmware update process..."
        execute_and_check "Deploying Driver,Firmware..." update_drivers_and_firmware_both \
                        "Gaudi Driver,Firmware updated successfully. Please reboot the machine for changes to take effect." \
                        "Failed to update Gaudi Driver,Firmware. Exiting."
    else
        echo "Gaudi driver and firmware update cancelled."
    fi
}

# Update drivers
update_drivers() {
    invoke_prereq_workflows
    echo "${YELLOW}Updating drivers...${NC}"
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-gaudi-firmware-driver.yml \
        --extra-vars "update_type=drivers"    
    echo "${GREEN}Drivers updated successfully!${NC}"
}

# Update firmware
update_firmware() {
    invoke_prereq_workflows
    echo "${YELLOW}Updating firmware...${NC}"
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-gaudi-firmware-driver.yml \
        --extra-vars "update_type=firmware"  
    echo "${GREEN}Firmware updated successfully!${NC}"
}

# Update both drivers and firmware
update_drivers_and_firmware_both() {
    update_drivers
    update_firmware
}

update_drivers_and_firmware() {    
    echo "-------------------------------------------------"
    echo "|        Update Drivers and Firmware             |"
    echo "|------------------------------------------------|"
    echo "| 1) Update Drivers                              |"
    echo "| 2) Update Firmware                             |"
    echo "| 3) Update Both Drivers and Firmware            |"
    echo "|------------------------------------------------|"
    echo "Please choose an option (1, 2, or 3):"
    read -p "> " update_choice
    case $update_choice in
        1)
            update_gaudi_drivers
            ;;
        2)
            update_gaudi_firmware
            ;;
        3)
            update_gaudi_driver_and_firmware_both
            ;;
        *)
            echo "Invalid option. Please enter 1, 2, or 3."
            update_drivers_and_firmware
            ;;
    esac
}

update_cluster() {          
    echo "-------------------------------------------------"
    echo "|             Update Existing Cluster            |"
    echo "|------------------------------------------------|"
    echo "| 1) Manage Worker Nodes                         |"
    echo "| 2) Manage LLM Models                           |"
    #echo "| 3) Update Driver and Firmware                  |"
    echo "|------------------------------------------------|"    
    echo "Please choose an option (1 or 2):"
    read -p "> " update_choice
    case $update_choice in
        1)
            manage_worker_nodes "$@"
            ;;
        2)
            manage_models "$@"
            ;;
        # 3)
        #     update_drivers_and_firmware "$@"
        #     ;;
        *)
            echo "Invalid option. Please enter 1 or 2."
            update_cluster
            ;;
    esac
}

manage_worker_nodes() {
    echo "-------------------------------------------------"
    echo "| Manage Worker Nodes                            |"
    echo "|------------------------------------------------|"
    echo "| 1) Add Worker Node                             |"
    echo "| 2) Remove Worker Node                          |"
    echo "|------------------------------------------------|"
    echo "Please choose an option (1 or 2):"
    read -p "> " worker_choice
    case $worker_choice in
        1)
            add_worker_node "$@"
            ;;
        2)
            remove_worker_node "$@"
            ;;
        *)
            echo "Invalid option. Please enter 1 or 2."
            manage_worker_nodes
            ;;
    esac
}



manage_models() {
    
    echo "-------------------------------------------------"
    echo "| Manage LLM Models                               "
    echo "|------------------------------------------------|"
    echo "| 1) Deploy Model                                |"
    echo "| 2) Undeploy Model                              |"
    echo "| 3) List Installed Models                       |"
    echo "| 4) Deploy Model from Hugging Face              |"
    echo "| 5) Remove Model using deployment name          |"
    echo "|------------------------------------------------|"
    echo "Please choose an option (1, 2, 3, or 4):"
    read -p "> " model_choice
    case $model_choice in
        1)
            add_model "$@"
            ;;
        2)
            remove_model "$@"
            ;;
        3)
            list_models "$@"
            ;;
        4)
            deploy_from_huggingface "$@"
            ;;
        5)
            remove_model_deployed_via_huggingface "$@"
            ;;
        *)
            echo "Invalid option. Please enter 1, 2, 3, or 4."
            manage_models
            ;;
    esac
}


list_models() {
    list_model_menu="skip"
    read_config_file        
    prompt_for_input      
    if [ -z "$cluster_url" ] || [ -z "$cert_file" ] || [ -z "$key_file" ] || [ -z "$keycloak_client_id" ] || [ -z "$keycloak_admin_user" ] || [ -z "$keycloak_admin_password" ]; then
        echo "Some required arguments are missing. Prompting for input..."
        prompt_for_input
    fi                
    setup_initial_env       
    execute_and_check "Listing Inference LLM Models..." list_inference_llm_models_playbook "$@" \
        "Inference LLM Model listed successfully." \
        "Failed to list Inference LLM Model Exiting!."    
}

remove_model_deployed_via_huggingface(){
    echo "-------------------------------------------------"
    echo "|         Removing Model using Deployment name   |"
    echo "|------------------------------------------------|"
    hugging_face_model_remove_deployment="true"
    read_config_file "$@"       
    prompt_for_input "$@"    
    if [ -z "$cluster_url" ] || [ -z "$cert_file" ] || [ -z "$key_file" ] || [ -z "$keycloak_client_id" ] || [ -z "$keycloak_admin_user" ] || [ -z "$keycloak_admin_password" ] || [ -z "$hugging_face_token" ] || [ -z "$models" ]; then
        echo "Some required arguments are missing. Prompting for input..."
        prompt_for_input "$@"
    fi
    read -p "${YELLOW}CAUTION: Removing the Inference LLM Model will also remove its associated services and resources, which may cause service downtime and potential data loss. This action is irreversible. Are you absolutely certain you want to proceed? (y/n) ${NC}" -r user_response    
    echo ""
    if [[ ! $user_response =~ ^[YyNn]([Ee][Ss])?$ ]]; then
        echo "Aborting LLM Model removal process. Exiting!!"
        exit 1
    fi        
    read -p "Enter the deployment name of the model you wish to deprovision: " hugging_face_model_remove_name
    if [ -n "$hugging_face_model_remove_name" ]; then
        setup_initial_env                
        execute_and_check "Removing Inference LLM Models..." remove_inference_llm_models_playbook "$@" \
            "Inference LLM Model is removed successfully." \
            "Failed to remove Inference LLM Model Exiting!."
        echo "---------------------------------------------------------------------"
        echo "|     LLM Model Being Removed from AI Inference as Service Cluster! |"
        echo "---------------------------------------------------------------------"
        echo ""        
    else
        echo "Required huggingface model name and model id not provided. Exiting!!"
    fi
}

deploy_from_huggingface() {
    echo "-------------------------------------------------"
    echo "|         Deploy Model from Huggingface          |"
    echo "|------------------------------------------------|"    
    hugging_face_model_deployment="true"
    read_config_file "$@"        
    prompt_for_input "$@"    
    if [ -z "$cluster_url" ] || [ -z "$cert_file" ] || [ -z "$key_file" ] || [ -z "$keycloak_client_id" ] || [ -z "$keycloak_admin_user" ] || [ -z "$keycloak_admin_password" ] || [ -z "$hugging_face_token" ] || [ -z "$models" ]; then
        echo "Some required arguments are missing. Prompting for input..."
        prompt_for_input
    fi        
        
    read -p "Enter the Huggingface Model ID: " huggingface_model_id    
    echo "${YELLOW}NOTICE: The model deployment name will be used as the release identifier for deployment. It must be unique, meaningful, and follow Kubernetes naming conventions — lowercase letters, numbers, and hyphens only. Capital letters or special characters are not allowed. ${NC}"
    read -p "Enter Deployment Name for the Model: " huggingface_model_deployment_name
    echo "${YELLOW}NOTICE: Ensure the Tensor Parallel size value corresponds to the number of available Gaudi cards. Providing an incorrect value may result in the model being in a not ready state. ${NC}" 
    if [ "$cpu_or_gpu" = "g" ]; then
        read -p "Enter the Tensor Parallel size:" -r huggingface_tensor_parellel_size        
        if ! [[ "$huggingface_tensor_parellel_size" =~ ^[0-9]+$ ]]; then
            echo "Invalid input: Tensor Parallel size must be a positive integer."
            exit 1
        fi 
    fi           
    if [ -n "$huggingface_model_deployment_name" ] && [ -n "$huggingface_model_id" ]; then
        read -p "${YELLOW}NOTICE: You are about to deploy a model directly from Hugging Face, which has not been pre-validated by our team. Do you wish to continue? (y/n) ${NC}" -r user_response
        echo ""
        if [[ ! $user_response =~ ^[YyNn]([Ee][Ss])?$ ]]; then        
            echo "Deployment process has been cancelled. Exiting!!"
            exit 1
        fi
        setup_initial_env                
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
        echo "https://github.com/intel-innersource/applications.ai.erag.infra-automation/tree/main/ida#accessing-deployed-models-for-inference"
        echo ""
        echo "Please refer to this comprehensive guide for detailed instructions."          
        echo ""
    else
        echo "Required huggingface model name and model id not provided. Exiting!!"
    fi
}

add_model() {
    read_config_file "$@"        
    prompt_for_input "$@"    
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
        if [[ ! $user_response =~ ^[YyNn]([Ee][Ss])?$ ]]; then
            echo "Deployment process has been cancelled. Exiting!!"
            exit 1
        fi
        setup_initial_env                
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
        echo "https://github.com/intel-innersource/applications.ai.erag.infra-automation/tree/main/ida#accessing-deployed-models-for-inference"
        echo ""
        echo "Please refer to this comprehensive guide for detailed instructions."          
        echo ""
    fi
}

remove_model() {
    read_config_file "$@"        
    prompt_for_input "$@"    
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
        if [[ ! $user_response =~ ^[YyNn]([Ee][Ss])?$ ]]; then
            echo "Aborting LLM Model removal process. Exiting!!"
            exit 1
        fi
        setup_initial_env       
        execute_and_check "Removing Inference LLM Models..." remove_inference_llm_models_playbook "$@" \
            "Inference LLM Model is removed successfully." \
            "Failed to remove Inference LLM Model Exiting!."
        echo -e "${BLUE}------------------------------------------------------------------------------${NC}"
        echo -e "${GREEN}|  AI LLM Model is being removed from AI Inference as Service Cluster!       |${NC}"
        echo -e "${GREEN}|  This may take some time depending on system resources and other factors.  |${NC}"
        echo -e "${GREEN}|  Please standby...                                                         |${NC}"
        echo -e "${BLUE}------------------------------------------------------------------------------${NC}"
    fi
}

add_worker_node() {
    echo "Adding a new worker node to the AI Inference as Service cluster..."    
    read -p "${YELLOW}WARNING: Adding a node that is already managed by another Kubernetes cluster or has been manually configured using kubeadm, kubelet, or other tools can cause severe disruptions to your existing cluster. This may lead to issues such as pod restarts, service interruptions, and potential data loss. Do you want to proceed? (y/n) ${NC}" -r user_response
    echo ""
    if [[ ! $user_response =~ ^[YyNn]([Ee][Ss])?$ ]]; then
        echo "Aborting node addition process. Exiting!!"
        exit 1
    fi
    execute_and_check "Adding new worker nodes..." add_inference_nodes_playbook "$@" \
            "Adding a new worker node to the cluster" \
            "Failed to add worker node Exiting!."
        
    echo -e "${BLUE}------------------------------------------------------------------------------${NC}"
    echo -e "${GREEN}|  Node is being added to the AI Inference as Service Cluster!              |${NC}"
    echo -e "${GREEN}|  This process depends on network and available system resources.          |${NC}"
    echo -e "${GREEN}|  Please stand by while the node is being added...                         |${NC}"
    echo -e "${BLUE}------------------------------------------------------------------------------${NC}"    
                
}


remove_worker_node() {
    echo "Removing a worker node from the AI Inference as Service cluster..."    
    read -p "${YELLOW}WARNING: Removing a worker node will drain all resources from the node, which may cause service interruptions or data loss. This process cannot be undone. Do you want to proceed? (y/n)${NC} " -r user_response
    if [[ ! $user_response =~ ^[YyNn]([Ee][Ss])?$ ]]; then
        echo "Aborting node removal process. Exiting!!"
        exit 1
    fi
    echo "Draining resources and detaching the worker node. This may take some time..."
    execute_and_check "Removing worker nodes..." remove_inference_nodes_playbook "$@" \
            "Removing  worker node is successful." \
            "Failed to remove worker node Exiting!."
    echo "-------------------------------------------------------------------"
    echo "|     Node is being removed from AI Inference as Service Cluster!    |"
    echo "--------------------------------------------------------------------"
    
}

main_menu() {
    parse_arguments "$@"
    echo "----------------------------------------------------------"
    echo "${BLUE}|  Intel AI for Enterprise Inference                      |${NC}"
    echo "|---------------------------------------------------------|"
    echo "| 1) Provision Inference as Service Cluster               |"
    echo "| 2) Decommission Existing Cluster                        |"
    echo "| 3) Update Deployed Inference Cluster                    |"    
    echo "|---------------------------------------------------------|"
    echo "Please choose an option (1, 2, or 3):"
    read -p "> " user_choice
    case $user_choice in
        1)
            fresh_installation "$@"
            ;;
        2)
            reset_cluster "$@"
            ;;
        3)
            update_cluster "$@"
            ;;        
        *)
            echo "Invalid option. Please enter 1, 2, or 3."
            main_menu
            ;;
    esac
}

main_menu "$@"

