# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_genai_gateway_playbook() {
    echo "Deploying GenAI Gateway Service..."
    echo "************************************"        
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-genai-gateway.yml --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} deploy_genai_gateway=${deploy_genai_gateway} model_name_list='${model_name_list//\ /,}'  genai_gateway_trace_chart_version=${genai_gateway_trace_chart_version} kubernetes_platform=${kubernetes_platform}" --vault-password-file "$vault_pass_file"
}
