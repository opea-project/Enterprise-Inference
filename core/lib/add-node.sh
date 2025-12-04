
# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


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

    ansible-playbook -i "${INVENTORY_PATH}" playbooks/cluster.yml --become --become-user=root --become-password-file="${BECOME_PASSWORD_FILE}"

    
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
