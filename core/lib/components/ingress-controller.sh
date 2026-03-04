# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_ingress_nginx_playbook() {
    echo "Deploying the Ingress NGINX Controller..."
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-ingress-controller.yml --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} ingress_controller=${ingress_controller}"  
}