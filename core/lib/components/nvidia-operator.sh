# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_deploy_nvidia_operator_playbook() {
    echo "Running the deploy-nvidia-operator.yml playbook to deploy the NVIDIA GPU Operator..."
    ansible-galaxy collection install community.kubernetes
    ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root --become-password-file="${BECOME_PASSWORD_FILE}" playbooks/deploy-nvidia-operator.yml
    if [ $? -eq 0 ]; then
        echo "The deploy-nvidia-operator.yml playbook ran successfully."
    else
        echo "The deploy-nvidia-operator.yml playbook encountered an error."
        exit 1
    fi
}
