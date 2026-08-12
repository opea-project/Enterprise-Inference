# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_edge_gateway_playbook() {
    echo "Deploying the Envoy Gateway Edge Controller..."
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-ingress-controller.yml --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} envoy_gateway_version=${envoy_gateway_version:-v1.2.0}"  
}