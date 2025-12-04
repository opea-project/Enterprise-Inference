# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_reset_playbook() {
    echo "Running the Ansible playbook to reset the cluster..."  
    delete_pv_on_purge="yes"          
    if [ "$uninstall_ceph" == "yes" ]; then
        # Uninstall Ceph storage as part of cluster reset
        echo "Running Ceph uninstall as part of cluster reset..."
        uninstall_ceph_cluster
    fi
        
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-keycloak-controller.yml --extra-vars "delete_pv_on_purge=${delete_pv_on_purge}"
    ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root --become-password-file="${BECOME_PASSWORD_FILE}" reset.yml -e "confirm_reset=yes reset_nodes=false"
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
