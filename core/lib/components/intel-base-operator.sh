# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

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
    ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root --become-password-file="${BECOME_PASSWORD_FILE}" playbooks/deploy-habana-ai-operator.yml --extra-vars "gaudi_operator=${gaudi_operator}"
    if [ $? -eq 0 ]; then
        echo "The deploy-habana-ai-operator.yml playbook ran successfully."
    else
        echo "The deploy-habana-ai-operator.yml playbook encountered an error."
        exit 1
    fi
}
