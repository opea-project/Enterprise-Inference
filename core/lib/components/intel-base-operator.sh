# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# shellcheck shell=bash
# This file is a library fragment sourced by core/inference-stack-deploy.sh.
# Configuration globals are defined in lib/system/config-vars.sh and populated by
# lib/system/precheck/read-config-file.sh, and are shared across the sourced fragments.
# shellcheck disable=SC2154

run_deploy_habana_ai_operator_playbook() {
    echo "Running the deploy-habana-ai-operator.yml playbook to deploy the habana-ai-operator..."
    ansible-galaxy collection install community.kubernetes
    if [[ "$gaudi_platform" == "gaudi2" ]]; then
        gaudi_operator="$gaudi2_operator"
    elif [[ "$gaudi_platform" == "gaudi3" ]]; then
        gaudi_operator="$gaudi3_operator"
    else
        gaudi_operator=""
    fi    
    if ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root playbooks/deploy-habana-ai-operator.yml --extra-vars "gaudi_operator=${gaudi_operator}"; then
        echo "The deploy-habana-ai-operator.yml playbook ran successfully."
    else
        echo "The deploy-habana-ai-operator.yml playbook encountered an error."
        exit 1
    fi
}