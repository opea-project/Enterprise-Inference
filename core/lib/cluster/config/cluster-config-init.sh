# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# shellcheck shell=bash
# This file is a library fragment sourced by core/inference-stack-deploy.sh.
# Configuration globals are defined in lib/system/config-vars.sh and populated by
# lib/system/precheck/read-config-file.sh, and are shared across the sourced fragments.
# shellcheck disable=SC2154

deploy_cluster_config_playbook() {       
    if [ "${deploy_observability}" = "yes" ]; then
        tags="deploy_cluster_dashboard"
    else
        tags=""        
    fi
    
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-cluster-config.yml --become --become-user=root --extra-vars "brownfield_deployment=${brownfield_deployment} secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file}" --tags "$tags" 
}