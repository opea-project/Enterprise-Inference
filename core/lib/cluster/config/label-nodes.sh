# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_label_nodes_playbook() {
    echo "Running the label-nodes.yml playbook to label Kubernetes nodes..."
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/label-nodes.yml --extra-vars "airgap_enabled=${airgap_enabled} jfrog_url=${jfrog_url} jfrog_username=${jfrog_username} jfrog_password=${jfrog_password}"
}
