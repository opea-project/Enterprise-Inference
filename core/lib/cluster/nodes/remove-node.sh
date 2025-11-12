# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

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