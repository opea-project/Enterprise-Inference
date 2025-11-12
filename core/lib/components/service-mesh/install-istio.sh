# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

deploy_istio_playbook() {
    echo "Deploying Istio playbook..."    
    if [ "$deploy_istio" = "yes" ]; then
        ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-istio.yml
    else
        echo "Skipping Istio deployment as deploy_istio is set to 'no'."
    fi
}