# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_deploy_intel_gpu_plugin_playbook() {
    echo "Running the deploy-intel-gpu-plugin.yml playbook to deploy the Intel GPU Plugin for Arc BMG..."
    ansible-galaxy collection install community.kubernetes
    ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root playbooks/deploy-intel-gpu-plugin.yml \
        --extra-vars "intel_gpu_plugin_version=${intel_gpu_plugin_version}"
    if [ $? -eq 0 ]; then
        echo "The deploy-intel-gpu-plugin.yml playbook ran successfully."
    else
        echo "The deploy-intel-gpu-plugin.yml playbook encountered an error."
        exit 1
    fi
}
