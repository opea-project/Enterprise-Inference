# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

deploy_cluster_config_playbook() {       
    if [ "${deploy_observability}" = "yes" ]; then
        tags="deploy_cluster_dashboard"
    else
        tags=""        
    fi
    
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-cluster-config.yml --become --become-user=root --extra-vars "brownfield_deployment=${brownfield_deployment} secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file}" --tags "$tags" 
}