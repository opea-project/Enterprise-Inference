#!/bin/bash
# Colors
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
BLUE=$(tput setaf 4)
CYAN=$(tput setaf 6)
NC=$(tput sgr0)



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

# Intel AI for Enterprise Inference Stack Deployment

# This deployment automates the setup, reset, and update of a Kubernetes cluster with Enterprise Inference using Ansible playbooks. 
# It includes functions for setting up a virtual environment, installing Kubernetes, deploying various components 
# (e.g., Habana AI Operator, Ingress NGINX Controller, Keycloak, GenAI Gateway), and managing models and worker nodes.

# Prerequisites


# 1. Gaudi Driver update, Firmware update and Reboot
# 2. core/inventory/hosts.yaml file should be updated with the correct IP addresses of the nodes.

# Usage

# To run the deployment, execute the following command in your terminal:

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

# 1. Provision Enterprise Inference Cluster: Perform a fresh installation of the Kubernetes cluster with Enterprise Inference.
# 2. Decommission Existing Cluster: Reset the existing Kubernetes cluster.
# 3. Update Deployed Inference Cluster: Update the existing Kubernetes cluster.

# Fresh Installation

# If you choose to perform a fresh installation, the script will prompt you for the necessary inputs and proceed with the following steps:

# 1. Prompt for Input: Collects the required inputs from the user.
# 2. Setup Initial Environment: Sets up the virtual environment and installs necessary dependencies.
# 3. Install Kubernetes: Installs Kubernetes and sets up the kubeconfig for the user.
# 4. Deploy Components: Deploys the selected components (Habana AI Operator, Ingress NGINX Controller, Keycloak, APISIX or GenAI Gateway and Models).

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

--------------------------------------------------
Intel AI for Enterprise Inference Stack Deployment
--------------------------------------------------

Usage: ./inference-stack-deploy.sh [OPTIONS]

Automates the deployment and lifecycle management of Intel AI for Enterprise Inference Stack.

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
deploy_genai_gateway=""
deploy_llm_models=""
deploy_istio=""
deploy_nri_balloon_policy=""
list_model_menu=""
apisix_enabled=""
ingress_enabled=""
deploy_keycloak=""
deploy_apisix=""
delete_pv_on_purge=""
prereq_executed=0
vault_pass_file=""
hugging_face_model_deployment=""
huggingface_model_id=""
huggingface_model_deployment_name=""
hugging_face_model_remove_deployment=""
hugging_face_model_remove_name=""
huggingface_tensor_parellel_size=""
deploy_ceph=""
gaudi_platform=""
gaudi_operator=""
gaudi2_values_file_path=""
gaudi3_values_file_path=""
python3_interpreter=""
skip_check=""
purge_inference_cluster=""
uninstall_ceph=""



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
        local metadata_config_file="$HOMEDIR/inventory/metadata/inference-metadata.cfg"
        if [ -f "$metadata_config_file" ]; then
            echo "Metadata configuration file found, setting vars!"
            echo "---------------------------------------"
            while IFS='=' read -r key value || [ -n "$key" ]; do                
                key=$(echo "$key" | xargs)
                value=$(echo "$value" | xargs)                
                printf "%s=%s\n" "$key" "$value" >> temp_env_vars_metadata
            done < "$metadata_config_file"            
            source temp_env_vars_metadata
            rm temp_env_vars_metadata
        else
            echo "Enterprise Inference Metadata configuration file not found"
            exit 1        
        fi
        if [[ -n "$vault_pass_code" ]]; then
            echo "Vault password is set."            
            echo -n "$vault_pass_code" > .vault-passfile
            vault_pass_file="$HOMEDIR/.vault-passfile"                        
        else
            echo "Vault password is not set. Please set it in the configuration file."            
        fi
        
        INVENTORY_ALL_FILE="$HOMEDIR"/inventory/all.yml        
        if [[ -n "$http_proxy" ]]; then
            sed -i -E "s|^[[:space:]]*#?[[:space:]]*http_proxy:.*|http_proxy: \"$http_proxy\"|" "$INVENTORY_ALL_FILE"
            sed -i -E "/^env_proxy:/,/^[^[:space:]]/s|^[[:space:]]*http_proxy:.*|  http_proxy: \"$http_proxy\"|" "$INVENTORY_ALL_FILE"
            export http_proxy
        fi

        if [[ -n "$https_proxy" ]]; then
            sed -i -E "s|^[[:space:]]*#?[[:space:]]*https_proxy:.*|https_proxy: \"$https_proxy\"|" "$INVENTORY_ALL_FILE"
            sed -i -E "/^env_proxy:/,/^[^[:space:]]/s|^[[:space:]]*https_proxy:.*|  https_proxy: \"$https_proxy\"|" "$INVENTORY_ALL_FILE"
            export https_proxy
        fi
                                
        if [[ -n "$no_proxy" ]]; then
            sed -i -E "/^env_proxy:/,/^[^[:space:]]/s|^[[:space:]]*no_proxy:.*|  no_proxy: \"$no_proxy\"|" "$INVENTORY_ALL_FILE"
            export no_proxy
        fi
        
        case "$cpu_or_gpu" in
            "c" | "cpu")
            cpu_or_gpu="c"
            deploy_habana_ai_operator="no"
            ;;
            "g" | "gpu" | "gaudi2" | "gaudi3")
            if [[ "$gaudi_platform" == "" ]]; then
                if [[ "$cpu_or_gpu" == "gaudi2" || "$cpu_or_gpu" == "gpu" || "$cpu_or_gpu" == "g" ]]; then
                    gaudi_platform="gaudi2"
                elif [[ "$cpu_or_gpu" == "gaudi3" ]]; then
                    gaudi_platform="gaudi3"
                fi
            fi
            cpu_or_gpu="g"
            deploy_habana_ai_operator="yes"            
            ;;
            *)
            echo "Invalid value for cpu_or_gpu. It should be 'c' or 'cpu' for CPU, or 'g', 'gpu', 'gaudi2', or 'gaudi3' for GPU."
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
        case "$deploy_genai_gateway" in
            "no")
                deploy_genai_gateway="no"                
                ;;
            "yes")
                deploy_genai_gateway="yes"                                
                ;;
            *)
                echo "Incorrect value for deploy_genai_gateway"
                exit 1
                ;;
        esac
        
        if [[ "$deploy_genai_gateway" == "yes" && "$deploy_keycloak_apisix" == "yes" ]]; then
            echo -e "${YELLOW}--------------------------------------------------------------------------${NC}"
            echo -e "${YELLOW}|  NOTICE:                                                                |${NC}"
            echo -e "${YELLOW}|  Both 'GenAI Gateway' and 'Keycloak & APISIX' cannot be enabled at      |${NC}"
            echo -e "${YELLOW}|  the same time.                                                         |${NC}"
            echo -e "${YELLOW}|  Please select either GenAI Gateway or Keycloak & APISIX                |${NC}"            
            echo -e "${YELLOW}--------------------------------------------------------------------------${NC}"
            exit 1
        fi


    else
        echo "Configuration file not found. Using default values or prompting for input."
    fi    




}

run_system_prerequisites_check() {
    echo "Running system prerequisites check..."
    echo "This will verify minimum system dependencies required for deployment."

    local missing_deps=()
    local warnings=()        
    echo "Checking essential system commands..."
    
    # Wait for dpkg lock to be released if present
    dpkg_lock_file="/var/lib/dpkg/lock"
    dpkg_lock_frontend="/var/lib/dpkg/lock-frontend"
    dpkg_lock_files=("$dpkg_lock_file" "$dpkg_lock_frontend")
    timeout=300
    for lock in "${dpkg_lock_files[@]}"; do
        waited=0
        if command -v lsof &>/dev/null; then
            while lsof "$lock" &>/dev/null && [ $waited -lt $timeout ]; do
                echo -e "${YELLOW}dpkg/apt process is using $lock (checked via lsof). Waiting for it to finish...${NC}"
                sleep 2
                waited=$((waited + 2))
            done
        elif command -v fuser &>/dev/null; then
            while fuser "$lock" &>/dev/null && [ $waited -lt $timeout ]; do
                echo -e "${YELLOW}dpkg/apt process is using $lock (checked via fuser). Waiting for it to finish...${NC}"
                sleep 2
                waited=$((waited + 2))
            done
        fi
        if [ $waited -ge $timeout ]; then
            if (command -v lsof &>/dev/null && lsof "$lock" &>/dev/null) || \
            (command -v fuser &>/dev/null && fuser "$lock" &>/dev/null); then
                echo -e "${RED}Timeout waiting for dpkg/apt lock file $lock to be released. Proceeding anyway.${NC}"
            fi
        fi
    done

    # Check for git
    if ! command -v git &> /dev/null; then
        missing_deps+=("git")
    else
        echo -e "${GREEN}✓ git found${NC}"
    fi
    
    


    # Check for python3 (version 3.10 or above) using configured interpreter
    if [ -z "$python3_interpreter" ]; then
        echo -e "${RED}✗ python3_interpreter not configured${NC}"
        missing_deps+=("python3 (interpreter not configured)")
    elif ! command -v "$python3_interpreter" &> /dev/null; then
        echo -e "${RED}✗ configured python interpreter not found: $python3_interpreter${NC}"
        missing_deps+=("python3")
    else
        # Check Python version using the configured interpreter
        python_version=$($python3_interpreter -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if $python3_interpreter -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            echo -e "${GREEN}✓ python3 found (version $python_version) at $python3_interpreter${NC}"
        else
            echo -e "${RED}✗ python3 version $python_version found at $python3_interpreter, but version 3.10+ required${NC}"
            missing_deps+=("python3 (version 3.10+)")
        fi
    fi
    
    # Check for curl (needed for pip installation)
    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    else
        echo -e "${GREEN}✓ curl found${NC}"
    fi
    
    # Check internet connectivity (essential for Docker images, packages, repositories)
    echo "Checking internet connectivity..."
    if command -v curl &> /dev/null; then
        # Test multiple reliable endpoints to ensure connectivity
        if curl -s --connect-timeout 10 --max-time 15 https://google.com > /dev/null 2>&1 || \
           curl -s --connect-timeout 10 --max-time 15 https://github.com > /dev/null 2>&1 || \
           curl -s --connect-timeout 10 --max-time 15 https://registry-1.docker.io > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Internet connectivity confirmed${NC}"
        else
            echo -e "${RED}✗ No internet connectivity detected${NC}"
            missing_deps+=("internet-connectivity")
        fi
    else
        # If curl is not available, we'll check this later after curl is installed
        warnings+=("Internet connectivity check skipped - curl not available")
    fi
    
    # Check if pip is available for the configured Python interpreter
    if [ -n "$python3_interpreter" ]; then
        if ! $python3_interpreter -m pip --version &> /dev/null; then
            missing_deps+=("pip")
        else
            pip_version=$($python3_interpreter -m pip --version 2>/dev/null | cut -d' ' -f2)
            echo -e "${GREEN}✓ pip found for $python3_interpreter (version $pip_version)${NC}"
        fi
    else
        warnings+=("python3_interpreter not configured - pip check skipped")
    fi
    
    # Check for virtualenv capability (can be installed via pip)
    if [ -n "$python3_interpreter" ] && ! $python3_interpreter -c "import venv" &> /dev/null && ! $python3_interpreter -c "import virtualenv" &> /dev/null; then
        warnings+=("virtualenv not available - will be installed during setup")
    else
        echo -e "${GREEN}✓ virtualenv capability found${NC}"
    fi
    
    # Display warnings
    if [ ${#warnings[@]} -gt 0 ]; then
        echo -e "${YELLOW}Warnings:${NC}"
        for warning in "${warnings[@]}"; do
            echo -e "${YELLOW}  ! $warning${NC}"
        done
    fi
    

    echo "Updating system package lists..."
    if command -v apt &> /dev/null; then
        echo "Updating package lists using apt Ubuntu..."
        if sudo apt update; then
            echo -e "${GREEN}Package lists updated successfully${NC}"
        else
            echo -e "${YELLOW}Package list update failed, continuing anyway${NC}"
        fi
    elif command -v dnf &> /dev/null; then
        echo "Updating package lists using dnf (RHEL/CentOS)..."
        if sudo dnf check-update || [ $? -eq 100 ]; then
            echo -e "${GREEN} Package lists updated successfully${NC}"
        else
            echo -e "${YELLOW} Package list update failed, continuing anyway${NC}"
        fi
    else
        echo -e "${YELLOW}Unknown package manager, skipping package list update${NC}"
    fi
    echo ""

    # Check if any critical dependencies are missing and handle appropriately
    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo -e "${RED}Missing critical system dependencies:${NC}"
        for dep in "${missing_deps[@]}"; do
            echo -e "${RED}  - $dep${NC}"
        done
        echo ""
        
        # Separate Python/pip issues, internet connectivity, and installable dependencies
        local python_issues=()
        local connectivity_issues=()
        local installable_deps=()
        
        for dep in "${missing_deps[@]}"; do
            if [[ "$dep" == "python3"* ]]; then
                python_issues+=("$dep")
            elif [[ "$dep" == "internet-connectivity" ]]; then
                connectivity_issues+=("$dep")
            else
                installable_deps+=("$dep")
            fi
        done
        
        # Handle internet connectivity issues first - EXIT IMMEDIATELY (cannot be auto-fixed)
        if [ ${#connectivity_issues[@]} -gt 0 ]; then
            echo -e "${RED}Critical connectivity requirements not met:${NC}"
            echo -e "${RED}  - Internet connectivity is required for:${NC}"
            echo -e "${RED}    * Pulling Docker images${NC}"
            echo -e "${RED}    * Downloading packages and dependencies${NC}"
            echo -e "${RED}    * Accessing container registries${NC}"
            echo -e "${RED}    * Cloning Git repositories${NC}"
            echo ""
            echo -e "${YELLOW}Please ensure internet connectivity and try again.${NC}"
            echo -e "${YELLOW}Common solutions:${NC}"
            echo -e "${YELLOW}  - Check network configuration${NC}"
            echo -e "${YELLOW}  - Verify firewall/proxy settings${NC}"
            echo -e "${YELLOW}  - Test: curl -I https://google.com${NC}"
            exit 1
        fi
        
        # Handle Python issues first - EXIT IMMEDIATELY (no user acknowledgment)
        if [ ${#python_issues[@]} -gt 0 ]; then
            echo -e "${RED}Critical Python requirements not met:${NC}"
            for issue in "${python_issues[@]}"; do
                echo -e "${RED}  - $issue${NC}"
            done
            echo ""
            echo -e "${YELLOW}Python 3.10+ is required for Enterprise Inference deployment.${NC}"
            echo -e "${YELLOW}Please install/configure Python 3.10+ and set python3_interpreter, then try again.${NC}"
            echo -e "${YELLOW}RHEL: dnf install python3 python3-pip${NC}"
            echo -e "${YELLOW}Ubuntu: apt update && apt install python3 python3-pip${NC}"
            exit 1
        fi
        
        # Handle installable dependencies (git, curl) with user acknowledgment
        if [ ${#installable_deps[@]} -gt 0 ]; then
            echo -e "${YELLOW}The following dependencies can be installed automatically:${NC}"
            for dep in "${installable_deps[@]}"; do
                echo -e "${YELLOW}  - $dep${NC}"
            done
            echo ""
            install_deps="yes"
            
            if [[ "$install_deps" =~ ^(yes|y|Y)$ ]]; then
                # Separate pip from other dependencies
                local pip_needed=false
                local other_deps=()
                
                for dep in "${installable_deps[@]}"; do
                    if [[ "$dep" == "pip" ]]; then
                        pip_needed=true
                    else
                        other_deps+=("$dep")
                    fi
                done
                
                # Install regular dependencies first (git, curl)
                if [ ${#other_deps[@]} -gt 0 ]; then
                    if command -v dnf &> /dev/null; then
                        echo "Installing dependencies using dnf RHEL..."
                        sudo dnf install -y "${other_deps[@]}"
                    elif command -v apt &> /dev/null; then
                        echo "Installing dependencies using apt Ubuntu..."
                        sudo apt update && sudo apt install -y "${other_deps[@]}"
                    else
                        echo -e "${RED}Unsupported package manager. This script supports RHEL (dnf) and Ubuntu (apt) only.${NC}"
                        echo -e "${YELLOW}Please install manually:${NC}"
                        echo -e "${YELLOW}  RHEL: dnf install ${other_deps[*]}${NC}"
                        echo -e "${YELLOW}  Ubuntu: apt install ${other_deps[*]}${NC}"
                        exit 1
                    fi
                fi
                
                # Install pip using system package manager if needed
                if [ "$pip_needed" = true ]; then
                    echo "Installing pip using system package manager..."
                    if command -v dnf &> /dev/null; then
                        python_version=$($python3_interpreter -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
                        if [[ "$python_version" == "3.11" ]]; then
                            echo "Installing python3.11-pip using dnf (RHEL 9)..."
                            if ! sudo dnf install -y python3.11-pip; then
                                echo -e "${RED}Failed to install python3.11-pip using dnf${NC}"
                                exit 1
                            fi
                        elif [[ "$python_version" == "3.12" ]]; then
                            echo "Installing python3.12-pip using dnf (RHEL 9)..."
                            if ! sudo dnf install -y python3.12-pip; then
                                echo -e "${RED}Failed to install python3.12-pip using dnf${NC}"
                                exit 1
                            fi
                        else
                            echo "Installing python3-pip using dnf (RHEL 9)..."
                            if ! sudo dnf install -y python3-pip; then
                                echo -e "${RED}Failed to install python3-pip using dnf${NC}"
                                exit 1
                            fi
                        fi
                    elif command -v apt &> /dev/null; then
                        echo "Installing python3-pip using apt (Ubuntu 22/24)..."
                        if ! sudo apt install -y python3-pip; then
                            echo -e "${RED}Failed to install python3-pip using apt${NC}"
                            exit 1
                        fi
                    else
                        echo -e "${RED}Unsupported system. This deployment only supports Ubuntu 22/24 and RHEL 9.4${NC}"
                        exit 1
                    fi
                fi
                
                # Verify installation
                local install_failed=()
                for dep in "${installable_deps[@]}"; do
                    if [[ "$dep" == "pip" ]]; then
                        if ! $python3_interpreter -m pip --version &> /dev/null; then
                            install_failed+=("$dep")
                        fi
                    else
                        if ! command -v "$dep" &> /dev/null; then
                            install_failed+=("$dep")
                        fi
                    fi
                done
                
                if [ ${#install_failed[@]} -gt 0 ]; then
                    echo -e "${RED}Failed to install: ${install_failed[*]}${NC}"
                    echo -e "${YELLOW}Please install them manually and try again.${NC}"
                    exit 1
                else
                    echo -e "${GREEN}All dependencies installed successfully!${NC}"
                fi
            else
                echo -e "${YELLOW}Installation cancelled. Please install the dependencies manually:${NC}"
                echo -e "${YELLOW}  RHEL: sudo dnf install ${installable_deps[*]}${NC}"
                echo -e "${YELLOW}  Ubuntu: sudo apt install ${installable_deps[*]}${NC}"
                exit 1
            fi
        fi
    fi
    
    echo -e "${GREEN}System prerequisites check completed successfully.${NC}"    
    return 0
}

run_infrastructure_readiness_check() {
    echo "Running infrastructure readiness check..."
    echo "This will verify system compatibility and infrastructure requirements."
        
    if [ ! -f "$HOMEDIR/inventory/hosts.yaml" ]; then
        echo -e "${RED}Error: Inventory file not found at $HOMEDIR/inventory/hosts.yaml${NC}"
        echo -e "${YELLOW}Please ensure the inventory file exists and contains the correct host information.${NC}"
        return 1
    fi    
    if ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root playbooks/inference-precheck.yml; then
        echo -e "${GREEN}Infrastructure readiness check completed successfully.${NC}"
        return 0
    else
        echo -e "${RED}Infrastructure readiness check failed. Please resolve the issues before proceeding.${NC}"
        return 1
    fi
}

setup_initial_env() {
    echo "Setting up the Initial Environment..."
    
    if [[ "$skip_check" != "true" ]]; then
        echo "Performing initial system prerequisites check..."
        if ! run_system_prerequisites_check; then
            echo "System prerequisites check failed. Please install missing dependencies and try again."
            exit 1
        fi
        echo "System prerequisites check completed successfully."
    else
        echo "Skipping system prerequisites check due to --skip-check argument."
    fi
        
    if [[ -n "$https_proxy" ]]; then
        git config --global http.proxy "$https_proxy"
        git config --global https.proxy "$https_proxy"
    fi
    if [ ! -d "$KUBESPRAYDIR" ]; then
        git clone https://github.com/kubernetes-sigs/kubespray.git $KUBESPRAYDIR
        if [ $? -ne 0 ] || [ ! -d "$KUBESPRAYDIR/.git" ]; then
            echo -e "${RED}----------------------------------------------------------------------------${NC}"
            echo -e "${RED}|  NOTICE: Failed to clone Kubespray Repository.                           |${NC}"        
            echo -e "${RED}|  Unable to proceed with Inference Stack Deployment                        |${NC}"        
            echo -e "${RED}|  due to missing dependency                                                |${NC}"        
            echo -e "${RED}----------------------------------------------------------------------------${NC}"            
            exit 1
        fi
        cd $KUBESPRAYDIR
        git checkout v2.27.0
    else
        echo "Kubespray directory already exists, skipping clone."
        cd $KUBESPRAYDIR
    fi
    if [[ -n "$https_proxy" ]]; then
        git config --global --unset http.proxy
        git config --global --unset https.proxy
    fi
    
    VENVDIR="$KUBESPRAYDIR/venv"
    REMOTEDIR="/tmp/helm-charts"    
    if [ ! -d "$VENVDIR" ]; then                
        echo "Installing python3-venv package..."
        if command -v apt &> /dev/null; then            
            python_version=$($python3_interpreter -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")            
            sudo apt install -y python${python_version}-venv || sudo apt install -y python3-venv        
        fi                
        if $python3_interpreter -m venv $VENVDIR; then
            echo "Virtual environment created within Kubespray directory."
        else
            echo -e "${RED}Failed to create virtual environment.${NC}"
            exit 1
        fi
    else
        echo "Virtual environment already exists within Kubespray directory, skipping creation."
    fi
    source $VENVDIR/bin/activate
    echo "Attempting to activate the virtual environment..."    
    if [ -z "$VIRTUAL_ENV" ]; then        
        rm -rf "$KUBESPRAYDIR"
        echo -e "${RED}----------------------------------------------------------------------------${NC}"
        echo -e "${RED}|  NOTICE: Failed to activate the virtual environment.                      |${NC}"
        echo -e "${RED}|  Please retrigger the Inference Stack Deployment                          |${NC}"
        echo -e "${RED}|                                                                           |${NC}"
        echo -e "${RED}----------------------------------------------------------------------------${NC}"
        exit 1
    else
        echo "Virtual environment activated successfully. Path: $VIRTUAL_ENV"
    fi                 
           
    export PIP_BREAK_SYSTEM_PACKAGES=1
    $VENVDIR/bin/python3 -m pip install --upgrade pip
    $VENVDIR/bin/python3 -m pip install -U -r requirements.txt    
    
    echo "Verifying Ansible Installation..."
    if $VENVDIR/bin/python3 -c "import ansible" &> /dev/null; then
        echo -e "${GREEN} Ansible installed successfully${NC}"
    else
        echo -e "${RED}----------------------------------------------------------------------------${NC}"
        echo -e "${RED}|  NOTICE: Ansible Installation Failed.                                     |${NC}"        
        echo -e "${RED}|  Unable to proceed with Inference Stack Deployment                        |${NC}"        
        echo -e "${RED}|  due to missing dependency                                                |${NC}"        
        echo -e "${RED}----------------------------------------------------------------------------${NC}"        
        exit 1
    fi    

    echo -e "${GREEN} Enterprise Inference requirements installed.${NC}"
    cp -r "$HOMEDIR"/deploy-* "$HOMEDIR"/helm-charts "$HOMEDIR"/scripts "$KUBESPRAYDIR"/
    cp -r "$KUBESPRAYDIR"/inventory/sample/ "$KUBESPRAYDIR"/inventory/mycluster
    cp  "$HOMEDIR"/inventory/hosts.yaml $KUBESPRAYDIR/inventory/mycluster/
    cp "$HOMEDIR"/inventory/metadata/addons.yml $KUBESPRAYDIR/inventory/mycluster/group_vars/k8s_cluster/addons.yml    
    cp "$HOMEDIR"/playbooks/* "$KUBESPRAYDIR"/playbooks/    
    gaudi2_values_file_path="$REMOTEDIR/vllm/gaudi-values.yaml"
    gaudi3_values_file_path="$REMOTEDIR/vllm/gaudi3-values.yaml"
    cp "$HOMEDIR"/inventory/metadata/addons.yml $KUBESPRAYDIR/inventory/mycluster/group_vars/k8s_cluster/addons.yml
    cp "$HOMEDIR"/inventory/metadata/all.yml $KUBESPRAYDIR/inventory/mycluster/group_vars/all/all.yml
    cp -r "$HOMEDIR"/roles/* $KUBESPRAYDIR/roles/        

    mkdir -p "$KUBESPRAYDIR/config"        
    chmod +x $HOMEDIR/scripts/generate-vault-secrets.sh

    # Only generate vault secrets if vault.yml doesn't exist or is incomplete
    vault_file="$HOMEDIR/inventory/metadata/vault.yml"
    mandatory_keys=("litellm_master_key" "litellm_salt_key" "redis_password" "langfuse_secret_key" "langfuse_public_key" "postgresql_username" "postgresql_password" "clickhouse_username" "clickhouse_password" "langfuse_login" "langfuse_user" "langfuse_password" "minio_secret" "minio_user" "postgres_user" "postgres_password")

    if [ ! -f "$vault_file" ]; then
        echo "vault.yml not found at $vault_file, generating vault secrets..."
        bash $HOMEDIR/scripts/generate-vault-secrets.sh
    else
        echo "Checking vault.yml for mandatory keys..."
        missing_keys=()
        for key in "${mandatory_keys[@]}"; do
            if ! grep -q "^${key}:" "$vault_file"; then
                missing_keys+=("$key")
            fi
        done

        if [ ${#missing_keys[@]} -gt 0 ]; then
            echo -e "${YELLOW}vault.yml exists but is missing mandatory keys: ${missing_keys[*]}${NC}"
            echo "Regenerating vault.yml with all mandatory keys..."
            bash $HOMEDIR/scripts/generate-vault-secrets.sh
        else
            echo -e "${GREEN}vault.yml exists and contains all mandatory keys. Skipping generation...${NC}"
        fi
    fi

    if [ "$purge_inference_cluster" != "purging" ]; then        
        if [[ "$deploy_llm_models" == "yes" || "$deploy_keycloak_apisix" == "yes" || "$deploy_genai_gateway" == "yes" || "$deploy_observability" == "yes" || "$deploy_logging" == "yes" || "$deploy_ceph" == "yes" || "$deploy_istio" == "yes" ]]; then
            if [ ! -s "$HOMEDIR/inventory/metadata/vault.yml" ]; then                
                echo -e "${YELLOW}----------------------------------------------------------------------------${NC}"
                echo -e "${YELLOW}|  NOTICE: inventory/metadata/vault.yml is empty!                           |${NC}"
                echo -e "${YELLOW}|  Please refer to docs/configuring-vault-values.md for instructions on     |${NC}"
                echo -e "${YELLOW}|  updating vault.yml                                                       |${NC}"
                echo -e "${YELLOW}----------------------------------------------------------------------------${NC}"
                exit 1
            fi      
        fi          
    fi    
    cp "$HOMEDIR"/inventory/metadata/vault.yml $KUBESPRAYDIR/config/vault.yml            
    mkdir -p "$KUBESPRAYDIR/config/vars" 
    cp -r "$HOMEDIR"/inventory/metadata/vars/* $KUBESPRAYDIR/config/vars/    
    cp "$HOMEDIR"/playbooks/* "$KUBESPRAYDIR"/playbooks/
    echo "Additional files and directories copied to Kubespray directory."
        
    if [[ "$skip_check" != "true" ]]; then
        echo "Performing infrastructure readiness check..."
        if ! run_infrastructure_readiness_check; then
            echo "Infrastructure readiness check failed. Please resolve the issues and try again."
            exit 1
        fi
    else
        echo "Skipping infrastructure readiness check due to --skip-check argument."
    fi
    echo "Infrastructure readiness check completed successfully."    
    gaudi2_values_file_path="$REMOTEDIR/vllm/gaudi-values.yaml"
    gaudi3_values_file_path="$REMOTEDIR/vllm/gaudi3-values.yaml"
    ansible-galaxy collection install community.kubernetes        
}


invoke_prereq_workflows() {
    if [ $prereq_executed -eq 0 ]; then
        read_config_file "$@"
        if [ -z "$cluster_url" ] || [ -z "$cert_file" ] || [ -z "$key_file" ] || [ -z "$keycloak_client_id" ] || [ -z "$keycloak_admin_user" ] || [ -z "$keycloak_admin_password" ]; then
            echo "Some required arguments are missing. Prompting for input..."
            prompt_for_input
        fi
        setup_initial_env "$@"
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
    if [ "$uninstall_ceph" == "yes" ]; then
        # Uninstall Ceph storage as part of cluster reset
        echo "Running Ceph uninstall as part of cluster reset..."
        uninstall_ceph_cluster
    fi
        
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
    echo "-----------------------------------------------------------"
    echo "|     Purge Cluster! Intel AI for Enterprise!             |"
    echo "-----------------------------------------------------------"
    echo "${YELLOW}NOTICE: You are initiating a reset of the existing Enterprise Inference Cluster."
    echo "This action will erase all current configurations, services and resources. Potentially causing service interruptions and data loss. This operation cannot be undone. ${NC}"
    read -p "Are you sure you want to proceed? (yes/no): " confirm_reset            
    if [[ "$confirm_reset" =~ ^(yes|y|Y)$ ]]; then
        echo "Resetting the existing Enterprise Inference cluster..."
        skip_check="true" 
        purge_inference_cluster="purging"        
        invoke_prereq_workflows "$@"
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
    if [[ "$gaudi_platform" == "gaudi2" ]]; then
        gaudi_operator="$gaudi2_operator"
    elif [[ "$gaudi_platform" == "gaudi3" ]]; then
        gaudi_operator="$gaudi3_operator"
    else
        gaudi_operator=""
    fi    
    ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root deploy-habana-ai-operator.yml --extra-vars "gaudi_operator=${gaudi_operator}"
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

run_genai_gateway_playbook() {
    echo "Deploying GenAI Gateway Service..."
    echo "************************************"        
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-genai-gateway.yml --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} deploy_genai_gateway=${deploy_genai_gateway} model_name_list='${model_name_list//\ /,}' " --vault-password-file "$vault_pass_file"
}

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
        echo "${GREEN}CPU deployment detected - using generic NRI balloon policy${NC}"
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
        
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-inference-models.yml \
        --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} keycloak_admin_user=${keycloak_admin_user} keycloak_admin_password=${keycloak_admin_password} keycloak_client_id=${keycloak_client_id} hugging_face_token=${hugging_face_token} install_true=${install_true} model_name_list='${model_name_list//\ /,}' cpu_playbook=${cpu_playbook} gpu_playbook=${gpu_playbook} hugging_face_token_falcon3=${hugging_face_token_falcon3} deploy_keycloak=${deploy_keycloak} apisix_enabled=${apisix_enabled} ingress_enabled=${ingress_enabled} gaudi_deployment=${gaudi_deployment} huggingface_model_id=${huggingface_model_id} hugging_face_model_deployment=${hugging_face_model_deployment} huggingface_model_deployment_name=${huggingface_model_deployment_name} deploy_inference_llm_models_playbook=${deploy_inference_llm_models_playbook} huggingface_tensor_parellel_size=${huggingface_tensor_parellel_size} deploy_genai_gateway=${deploy_genai_gateway} vllm_metrics_enabled=${vllm_metrics_enabled} gaudi_values_file=${gaudi_values_file} deploy_ceph=${deploy_ceph} enable_cpu_balloons=${enable_cpu_balloons}" --tags "$tags" --vault-password-file "$vault_pass_file"

}

deploy_ceph_cluster() {

    echo "Deploying Ceph Cluster..."

    echo "Generating Ceph configuration values..."
    if ! ansible-playbook -i "${INVENTORY_PATH}" playbooks/generate-ceph-values.yml; then
        echo -e "${RED}Failed to generate Ceph configuration values.${NC}"
        echo -e "${YELLOW}Please check the inventory configuration and try again.${NC}"
        return 1
    fi

    echo "Deploying Ceph storage cluster..."
    if ! ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-ceph-storage.yml; then
        echo -e "${RED} Ceph Cluster deployment FAILED!${NC}"
        echo ""
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}│                        CEPH DEPLOYMENT FAILURE                           │${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}│  Common causes and solutions:                                            │${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}│  1. Previous Ceph installation exists:                                   │${NC}"
        echo -e "${YELLOW}│     • Run this script with 'uninstall_ceph=on' in config                 │${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}│  2. Storage devices need formatting:                                     │${NC}"
        echo -e "${YELLOW}│     • Check available devices                                            │${NC}"
        echo -e "${YELLOW}│     • Format devices if needed                                           │${NC}"
        echo -e "${YELLOW}│     • Remove any existing partitions                                     │${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}│  3. Insufficient resources:                                              │${NC}"
        echo -e "${YELLOW}│     • Ensure nodes have enough CPU, memory, and storage                  │${NC}"
        echo -e "${YELLOW}│     • Check node readiness: kubectl get nodes                            │${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}│  4. Network/connectivity issues:                                         │${NC}"
        echo -e "${YELLOW}│     • Verify all nodes can communicate                                   │${NC}"
        echo -e "${YELLOW}│     • Check firewall rules and port accessibility                        │${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}│                                                                                 │${NC}"
        echo -e "${YELLOW}│  RECOMMENDED ACTIONS:                                                           │${NC}"
        echo -e "${YELLOW}│                                                                                 │${NC}"
        echo -e "${YELLOW}│  1. Clean up any previous Ceph installation:                                    │${NC}"
        echo -e "${YELLOW}│     • Set 'uninstall_ceph=on' in inference-config.cfg                           │${NC}"
        echo -e "${YELLOW}│     • Run the deployment script again                                           │${NC}"
        echo -e "${YELLOW}│                                                                                 │${NC}"
        echo -e "${YELLOW}│  2. Format storage devices if required:                                         │${NC}"
        echo -e "${YELLOW}│     • sudo wipefs -a /dev/<device> (replace <device> with your storage device)  │${NC}"
        echo -e "${YELLOW}│     • sudo sgdisk --zap-all /dev/<device>                                       │${NC}"
        echo -e "${YELLOW}│     • sudo dd if=/dev/<device> of=/dev/<device> bs=1M status=progress           │${NC}"
        echo -e "${YELLOW}│                                                                                 │${NC}"
        echo -e "${YELLOW}│  3. Verify system requirements and try again                                    │${NC}"
        echo -e "${YELLOW}│                                                                                 │${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "${RED}Ceph deployment failed. Please address the issues above and retry.${NC}"
        return 1
    fi

    echo -e "${GREEN} Ceph Cluster deployed successfully!${NC}"
    return 0
        
}

uninstall_ceph_cluster() {

    echo "Uninstalling Ceph Cluster..."
    echo "WARNING: This will PERMANENTLY DELETE ALL CEPH DATA!"
    
    # Always attempt to run the uninstall playbook, but handle failures gracefully
    echo "Attempting Ceph cluster uninstall (if installed)..."
    if ansible-playbook -i "${INVENTORY_PATH}" playbooks/uninstall-ceph-storage.yml; then
        echo "Ceph cluster uninstall completed successfully."
    else
        echo "Warning: Ceph cluster uninstall encountered issues or Ceph may not be installed."
        echo "This is expected if no Ceph cluster was deployed."
    fi
        
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
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-observability.yml --become --become-user=root --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} deploy_observability=${deploy_observability} deploy_logging=${deploy_logging}" --tags "$tags" --vault-password-file "$vault_pass_file"
    
}

deploy_istio_playbook() {
    echo "Deploying Istio playbook..."    
    if [ "$deploy_istio" = "yes" ]; then
        ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-istio.yml
    else
        echo "Skipping Istio deployment as deploy_istio is set to 'no'."
    fi
}

deploy_nri_balloons_playbook() {
    echo "Deploying CPU Optimization (NRI Balloons & Topology Detection)..."
    
    # Strict CPU deployment check
    if [[ "$cpu_or_gpu" != "c" ]]; then
        echo "${RED}Error: CPU optimization can only be deployed for CPU deployments${NC}"
        echo "${RED}Current cpu_or_gpu setting: '$cpu_or_gpu'${NC}"
        echo "${RED}CPU optimization is specifically designed for CPU resource management${NC}"
        exit 1
    fi
    
    if [ "$deploy_nri_balloon_policy" == "yes" ] || [ "$cpu_or_gpu" == "c" ]; then
        echo "${GREEN}Deploying CPU optimization with topology detection and NRI balloon policy${NC}"
        ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-cpu-optimization.yml --extra-vars "cpu_playbook=true"
        if [ $? -eq 0 ]; then
            echo "${GREEN}CPU optimization deployed successfully${NC}"
        else
            echo "${RED}CPU optimization deployment failed${NC}"
            exit 1
        fi
    else
        echo "${YELLOW}Skipping CPU optimization - not a CPU deployment${NC}"
    fi
}

deploy_cluster_config_playbook() {       
    if [ "${deploy_observability}" = "yes" ]; then
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
        --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} keycloak_admin_user=${keycloak_admin_user} keycloak_admin_password=${keycloak_admin_password} keycloak_client_id=${keycloak_client_id} hugging_face_token=${hugging_face_token} uninstall_true=${uninstall_true} model_name_list='${model_name_list//\ /,}' hugging_face_model_remove_deployment=${hugging_face_model_remove_deployment} hugging_face_model_remove_name=${hugging_face_model_remove_name} deploy_ceph=${deploy_ceph}" --tags "$tags" --vault-password-file "$vault_pass_file" 
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

    invoke_prereq_workflows "$@"     

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
    invoke_prereq_workflows "$@"
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
        --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} keycloak_admin_user=${keycloak_admin_user} keycloak_admin_password=${keycloak_admin_password} keycloak_client_id=${keycloak_client_id} hugging_face_token=${hugging_face_token} uninstall_true=${uninstall_true} list_model_true='${list_model_true//\ /,}'" --vault-password-file "$vault_pass_file"
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

    if [ -z "$deploy_genai_gateway" ]; then
        read -p "Do you want to proceed with deploying GenAI Gateway? (yes/no): " deploy_genai_gateway
    else
        echo "Proceeding with the setup of GenAI Gateway: $deploy_genai_gateway"
    fi
    
    if [ -z "$deploy_observability" ]; then
        read -p "Do you want to proceed with deploying Observability? (yes/no): " deploy_observability
    else
        echo "Proceeding with the setup of Observability: $deploy_observability"
    fi

    if [ -z "$deploy_ceph" ]; then
        read -p "Do you want to proceed with deploying Ceph cluster setup? (yes/no): " deploy_ceph
    else
        echo "Proceeding with the setup of Ceph cluster: $deploy_ceph"
    fi
    
    if [ "$deploy_kubernetes_fresh" == "no" ]; then
        if [ -z "$uninstall_ceph" ]; then
            read -p "Do you want to proceed with uninstalling Ceph cluster? (yes/no): " uninstall_ceph
        else
            echo "Proceeding with Ceph cluster uninstallation: $uninstall_ceph"
        fi
    fi
           
    if [ -z "$deploy_istio" ]; then
        read -p "Do you want to proceed with deploying Istio? (yes/no): " deploy_istio
    else
        echo "Proceeding with the setup of Istio: $deploy_istio"
    fi

    if [ -z "$deploy_nri_balloon_policy" ]; then
        # Automatically enable NRI balloon policy for CPU deployments
        if [ "$cpu_or_gpu" == "c" ]; then
            deploy_nri_balloon_policy="yes"
            echo "NRI CPU Balloon Policy automatically enabled for CPU deployment"
        else
            deploy_nri_balloon_policy="no"
            echo "NRI CPU Balloon Policy disabled for GPU deployment"
        fi
    else
        echo "Proceeding with the setup of NRI CPU Balloon Policy: $deploy_nri_balloon_policy"
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
    if [ $deploy_keycloak == "yes" ]; then
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
                            echo "12. llama-3-3-70b"
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
            --deploy-nri-balloon-policy) deploy_nri_balloon_policy="$2"; shift ;;
            --skip-check) skip_check="true" ;;
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
            12)
                if [ "$cpu_or_gpu" = "c" ]; then
                    echo "Error: GPU model identifier provided for CPU deployment/removal." >&2
                    exit 1
                fi
                model_names+=("llama-3-3-70b")
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
            "llama-8b"|"llama-70b"|"codellama-34b"|"mixtral-8x-7b"|"mistral-7b"|"tei"|"tei-rerank"|"falcon3-7b"|"deepseek-r1-distill-qwen-32b"|"deepseek-r1-distill-llama8b"|"llama3-405b"|"llama-3-3-70b")
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
    if [[ "$deploy_kubernetes_fresh" == "no" && "$deploy_habana_ai_operator" == "no" && "$deploy_ingress_controller" == "no" && "$deploy_keycloak" == "no" && "$deploy_apisix" == "no" && "$deploy_llm_models" == "no" && "$deploy_observability" == "no" && "$deploy_genai_gateway" == "no" && "$deploy_istio" == "no" && "$deploy_ceph" == "no" && "$uninstall_ceph" == "no"  && "$deploy_nri_balloon_policy" == "no" ]]; then
    
    # Check if all deployment steps are set to "no" after getting user input  
        echo "No installation or deployment steps selected. Skipping setup_initial_env..."
        echo "--------------------------------------------------------------------"
        echo "|     Deployment Skipped for Intel AI for Enterprise Inference!    |"
        echo "--------------------------------------------------------------------"
    else
        prompt_for_input                        
        read -p "${YELLOW}ATTENTION: Ensure that the nodes do not contain existing workloads. If necessary, please purge any previous cluster configurations before initiating a fresh installation to avoid an inappropriate cluster state. Proceeding without this precaution could lead to service disruptions or data loss. Do you wish to continue with the setup? (yes/no) ${NC}" -r proceed_with_installation        
        
        if [[ "$proceed_with_installation" =~ ^([yY][eE][sS]|[yY])+$ ]]; then      
            echo "Starting fresh installation of Intel AI for Enterprise Inference Cluster..."    
            setup_initial_env                
            if [[ "$deploy_kubernetes_fresh" == "yes" ]]; then
                install_kubernetes "$@"
            else
                echo "Skipping Kubernetes installation..."
            fi
            execute_and_check "Deploying Cluster Configuration Playbook..." deploy_cluster_config_playbook \
                  "Cluster Configuration Playbook is deployed successfully." \
                  "Failed to deploy Cluster Configuration Playbook. Exiting."

            # Deploy NRI CPU Balloons for CPU deployments (after all infrastructure, before models)
            if [[ "$deploy_nri_balloon_policy" == "yes" ]]; then
                # Ensure this is a CPU deployment
                if [[ "$cpu_or_gpu" != "c" ]]; then
                    echo "${RED}Error: NRI Balloon Policy can only be deployed for CPU deployments (cpu_or_gpu='c')${NC}"
                    echo "${RED}Current cpu_or_gpu setting: '$cpu_or_gpu'${NC}"
                    echo "${RED}Please set cpu_or_gpu to 'c' or disable NRI balloon policy deployment. Exiting!${NC}"
                    exit 1
                fi
                execute_and_check "Deploying CPU Optimization (NRI Balloons & Topology Detection)..." deploy_nri_balloons_playbook "$@" \
                    "CPU optimization deployed successfully." \
                    "Failed to deploy CPU optimization. Exiting!."
            else
                echo "Skipping CPU optimization deployment..."
            fi
            
            if [[ "$deploy_habana_ai_operator" == "yes" ]]; then
                execute_and_check "Deploying habana-ai-operator..." run_deploy_habana_ai_operator_playbook "Habana AI Operator is deployed." \
                    "Failed to deploy Habana AI Operator. Exiting."
            else
                echo "Skipping Habana AI Operator installation..."
            fi

            if [[ "$uninstall_ceph" == "yes" ]]; then
                execute_and_check "Uninstalling CEPH storage..." uninstall_ceph_cluster "$@" \
                    "CEPH is uninstalled successfully." \
                    "Failed to uninstall CEPH. Exiting!."
            else
                echo "Skipping CEPH storage uninstallation..."
            fi

            if [[ "$deploy_ceph" == "yes" ]]; then
                execute_and_check "Deploying CEPH storage..." deploy_ceph_cluster "$@" \
                    "CEPH is deployed successfully." \
                    "Failed to deploy CEPH. Please use uninstall_ceph option to clean previous installation and format devices if needed."
            else
                echo "Skipping CEPH storage deployment..."
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
            
            if [[ "$deploy_genai_gateway" == "yes" ]]; then
                echo "successfully deploying genai gateway"
                execute_and_check "Deploying GenAI Gateway..." run_genai_gateway_playbook \
                    "GenAI Gateway is deployed successfully." \
                    "Failed to deploy GenAI Gateway. Exiting."                
            else
                echo "Skipping GenAI Gateway deployment..."
            fi
            
            if [[ "$deploy_observability" == "yes" ]]; then
                echo "Deploying observability..."
                execute_and_check "Deploying Observability..." deploy_observability_playbook "$@" \
                    "Observability is deployed successfully." \
                    "Failed to deploy Observability. Exiting!."
            else
                echo "Skipping Observability deployment..."
            fi
            
            if [[ "$deploy_istio" == "yes" ]]; then
                echo "Deploying Istio..."
                execute_and_check "Deploying Istio..." deploy_istio_playbook "$@" \
                    "Istio is deployed successfully." \
                    "Failed to deploy Istio. Exiting!."
            else
                echo "Skipping Istio deployment..."
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
            echo "https://github.com/opea-project/Enterprise-Inference/blob/main/docs/accessing-deployed-models.md"
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
            echo "https://github.com/opea-project/Enterprise-Inference/blob/main/docs/accessing-deployed-models.md"
            echo ""
            echo "Please refer to this comprehensive guide for detailed instructions." 
            echo "" 
            fi                     
        else
            echo "-------------------------------------------------------------------"
            echo "|     Deployment Skipped for Intel AI for Enterprise Inference!    |"
            echo "--------------------------------------------------------------------"
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
    invoke_prereq_workflows       
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
        user_response=$(echo "$user_response" | tr '[:upper:]' '[:lower:]')        
        if [[ ! $user_response =~ ^(yes|y|Y|YES)$ ]]; then        
            echo "Deployment process has been cancelled. Exiting!!"
            exit 1
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

remove_model() {
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

add_worker_node() {
    echo "Adding a new worker node to the Intel AI for Enterprise Inference cluster..."
    read -p "${YELLOW}WARNING: Adding a node that is already managed by another Kubernetes cluster or has been manually configured using kubeadm, kubelet, or other tools can cause severe disruptions to your existing cluster. This may lead to issues such as pod restarts, service interruptions, and potential data loss. Do you want to proceed? (y/n) ${NC}" -r user_response
    echo ""    
    user_response=$(echo "$user_response" | tr '[:upper:]' '[:lower:]')        
    if [[ ! $user_response =~ ^(yes|y|Y|YES)$ ]]; then            
        echo "Aborting node addition process. Exiting!!"
        exit 1
    fi
    skip_check="true"
    execute_and_check "Adding new worker nodes..." add_inference_nodes_playbook "$@" \
            "Adding a new worker node to the cluster" \
            "Failed to add worker node Exiting!."
        
    echo -e "${BLUE}------------------------------------------------------------------------------${NC}"
    echo -e "${GREEN}|  Node is being added to the Intel AI for Enterprise Inference Cluster!    |${NC}"
    echo -e "${GREEN}|  This process depends on network and available system resources.          |${NC}"
    echo -e "${GREEN}|  Please stand by while the node is being added...                         |${NC}"
    echo -e "${BLUE}------------------------------------------------------------------------------${NC}"    


    #Rerun baloon policy if its cpu deployment
    if [[ "$cpu_or_gpu" == "c" ]]; then
        echo "Reapplying NRI CPU Balloons for CPU deployments..."
        execute_and_check "Reapplying NRI CPU Balloons..." deploy_nri_balloons_playbook "$@" \
            "NRI CPU Balloons re-applied successfully." \
            "Failed to reapply NRI CPU Balloons. Exiting!."
        echo -e "${BLUE}------------------------------------------------------------------------------${NC}"
        echo -e "${GREEN}|  NRI CPU Balloons re-applied successfully!                                |${NC}"
        echo -e "${GREEN}|  This process may take some time depending on system resources.     |${NC}"
        echo -e "${GREEN}|  Please stand by while the NRI CPU Balloons are being re-applied... |${NC}"
        echo -e "${BLUE}------------------------------------------------------------------------------${NC}"
    fi           
}


remove_worker_node() {
    echo "Removing a worker node from the Intel AI for Enterprise Inference cluster..."
    read -p "${YELLOW}WARNING: Removing a worker node will drain all resources from the node, which may cause service interruptions or data loss. This process cannot be undone. Do you want to proceed? (y/n)${NC} " -r user_response
    user_response=$(echo "$user_response" | tr '[:upper:]' '[:lower:]')        
    if [[ ! $user_response =~ ^(yes|y|Y|YES)$ ]]; then        
        echo "Aborting node removal process. Exiting!!"
        exit 1
    fi
    echo "Draining resources and detaching the worker node. This may take some time..."
    skip_check="true"
    execute_and_check "Removing worker nodes..." remove_inference_nodes_playbook "$@" \
            "Removing  worker node is successful." \
            "Failed to remove worker node Exiting!."
    echo "------------------------------------------------------------------------"
    echo "|     Node is being removed from Intel AI for Enterprise Inference!    |"
    echo "------------------------------------------------------------------------"
    
}

main_menu() {
    parse_arguments "$@"
    echo "${BLUE}----------------------------------------------------------${NC}"
    echo "${BLUE}|  Intel AI for Enterprise Inference                      |${NC}"
    echo "${BLUE}|---------------------------------------------------------|${NC}"
    echo "| ${CYAN}1)${NC} Provision Enterprise Inference Cluster               |"
    echo "| ${CYAN}2)${NC} Decommission Existing Cluster                        |"
    echo "| ${CYAN}3)${NC} Update Deployed Inference Cluster                    |"    
    echo "${BLUE}|---------------------------------------------------------|${NC}"
    echo "Please choose an option (${CYAN}1${NC}, ${CYAN}2${NC}, or ${CYAN}3${NC}):"
    read -p "${CYAN}> ${NC}" user_choice
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
