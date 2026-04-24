# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_deploy_habana_ai_operator_playbook() {
    echo "Running the deploy-habana-ai-operator.yml playbook to deploy the habana-ai-operator..."
    if [[ "$airgap_enabled" != "yes" ]]; then
        ansible-galaxy collection install kubernetes.core
    fi
    if [[ "$gaudi_platform" == "gaudi2" ]]; then
        gaudi_operator="$gaudi2_operator"
    elif [[ "$gaudi_platform" == "gaudi3" ]]; then
        gaudi_operator="$gaudi3_operator"
    else
        gaudi_operator=""
    fi    
    ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root playbooks/deploy-habana-ai-operator.yml --extra-vars "gaudi_operator=${gaudi_operator} airgap_enabled=${airgap_enabled} jfrog_url=${jfrog_url} jfrog_username=${jfrog_username} jfrog_password=${jfrog_password}"
    if [ $? -eq 0 ]; then
        echo "The deploy-habana-ai-operator.yml playbook ran successfully."
    else
        echo "The deploy-habana-ai-operator.yml playbook encountered an error."
        exit 1
    fi
}