# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_keycloak_playbook() {
    echo "Deploying Keycloak using Ansible playbook..."
    install_ansible_collection    
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-keycloak-controller.yml
}

create_keycloak_tls_secret_playbook() {
    echo "Deploying Keycloak TLS secret playbook..."    
    echo "************************************"        
    
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-keycloak-tls-cert.yml \
        --extra-vars "kubernetes_platform=${kubernetes_platform} secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} keycloak_admin_user=${keycloak_admin_user} keycloak_admin_password=${keycloak_admin_password} keycloak_client_id=${keycloak_client_id} hugging_face_token=${hugging_face_token} model_name_list='${model_name_list//\ /,}'  deploy_keycloak=${deploy_keycloak}  deploy_apisix=${deploy_apisix} keycloak_chart_version=${keycloak_chart_version}"
}


