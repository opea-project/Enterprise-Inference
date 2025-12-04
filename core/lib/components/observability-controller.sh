# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

deploy_observability_playbook() {
    tags=""
    if [ "${deploy_observability}" = "yes" ]; then
        tags+="deploy_observability,"
    fi
    if [ "${deploy_logging}" = "yes" ]; then
        tags+="deploy_logging,"
    fi
    tags="${tags%,}"            
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-observability.yml --become --become-user=root --become-password-file="${BECOME_PASSWORD_FILE}" --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} deploy_observability=${deploy_observability} deploy_logging=${deploy_logging} observability_stack_chart_version=${observability_stack_chart_version}" --tags "$tags" --vault-password-file "$vault_pass_file"
    
}
