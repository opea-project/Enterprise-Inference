#!/bin/bash
# Colors
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
BLUE=$(tput setaf 4)
CYAN=$(tput setaf 6)
NC=$(tput sgr0)


# Copyright (C) 2025-2026 Intel Corporation
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

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# System configuration
source "$SCRIPT_DIR/lib/system/config-vars.sh"
source "$SCRIPT_DIR/lib/system/execute-and-check.sh"
source "$SCRIPT_DIR/lib/system/setup-env.sh"

# System prechecks
source "$SCRIPT_DIR/lib/system/precheck/read-config-file.sh"
source "$SCRIPT_DIR/lib/system/precheck/prereq-check.sh"
source "$SCRIPT_DIR/lib/system/precheck/readiness-check.sh"

# Cluster management
source "$SCRIPT_DIR/lib/cluster/config/cluster-config-init.sh"
source "$SCRIPT_DIR/lib/cluster/config/setup-user-cluster-config.sh"
source "$SCRIPT_DIR/lib/cluster/config/label-nodes.sh"
source "$SCRIPT_DIR/lib/cluster/state/cluster-state-check.sh"
source "$SCRIPT_DIR/lib/cluster/deployment/fresh-install.sh"
source "$SCRIPT_DIR/lib/cluster/deployment/cluster-update.sh"
source "$SCRIPT_DIR/lib/cluster/deployment/cluster-purge.sh"
source "$SCRIPT_DIR/lib/cluster/nodes/add-node.sh"
source "$SCRIPT_DIR/lib/cluster/nodes/remove-node.sh"
source "$SCRIPT_DIR/lib/cluster/drv-fw-update.sh"

# Components deployment
source "$SCRIPT_DIR/lib/components/kubernetes-setup.sh"
source "$SCRIPT_DIR/lib/components/intel-base-operator.sh"
source "$SCRIPT_DIR/lib/components/ingress-controller.sh"
source "$SCRIPT_DIR/lib/components/keycloak-controller.sh"
source "$SCRIPT_DIR/lib/components/genai-gateway-controller.sh"
source "$SCRIPT_DIR/lib/components/observability-controller.sh"
source "$SCRIPT_DIR/lib/components/storage/install-ceph-cluster.sh"
source "$SCRIPT_DIR/lib/components/storage/uninstall-ceph-cluster.sh"
source "$SCRIPT_DIR/lib/components/service-mesh/install-istio.sh"

# Model management
source "$SCRIPT_DIR/lib/models/model-selection.sh"
source "$SCRIPT_DIR/lib/models/list-model.sh"
source "$SCRIPT_DIR/lib/models/install-model.sh"
source "$SCRIPT_DIR/lib/models/uninstall-model.sh"
source "$SCRIPT_DIR/lib/models/install-model-hf.sh"
source "$SCRIPT_DIR/lib/models/uninstall-model-hf.sh"

# Xeon-specific optimizations
source "$SCRIPT_DIR/lib/xeon/ballon-policy.sh"

# User interface
source "$SCRIPT_DIR/lib/user-menu/parse-user-prompts.sh"
source "$SCRIPT_DIR/lib/user-menu/user-menu.sh"

# Brownfield deployment
source "$SCRIPT_DIR/lib/brownfield/brownfield_deployment.sh"


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

main_menu() {
    parse_arguments "$@"
    echo "${BLUE}----------------------------------------------------------${NC}"
    echo "${BLUE}|  Intel AI for Enterprise Inference                      |${NC}"
    echo "${BLUE}|---------------------------------------------------------|${NC}"
    echo "| ${CYAN}1)${NC} Provision Enterprise Inference Cluster               |"
    echo "| ${CYAN}2)${NC} Decommission Existing Cluster                        |"
    echo "| ${CYAN}3)${NC} Update Deployed Inference Cluster                    |"
    echo "| ${CYAN}4)${NC} Brownfield Deployment of Enterprise Inference        |"
    echo "${BLUE}|---------------------------------------------------------|${NC}"
    echo "Please choose an option (${CYAN}1${NC}, ${CYAN}2${NC}, ${CYAN}3${NC} or ${CYAN}4${NC}):"
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
        4)
            brownfield_deployment "$@"
            ;;        
        *)
            echo "Invalid option. Please enter 1, 2, 3 or 4."
            main_menu
            ;;
    esac
}

main_menu "$@"
