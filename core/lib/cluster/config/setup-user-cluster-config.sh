# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_kube_conf_copy_playbook() {
    echo "Running the setup-user-kubeconfig.yml playbook to set up kubeconfig for the user..."
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/setup-user-kubeconfig.yml
}