<<<<<<< HEAD
# Copyright (C) 2025-2026 Intel Corporation
=======
# Copyright (C) 2024-2025 Intel Corporation
>>>>>>> dell-deploy-1.4-nv
# SPDX-License-Identifier: Apache-2.0

run_label_nodes_playbook() {
    echo "Running the label-nodes.yml playbook to label Kubernetes nodes..."
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/label-nodes.yml
}
