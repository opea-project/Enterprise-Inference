# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# shellcheck shell=bash
# This file is a library fragment sourced by core/inference-stack-deploy.sh.
# Configuration globals are defined in lib/system/config-vars.sh and populated by
# lib/system/precheck/read-config-file.sh, and are shared across the sourced fragments.
# shellcheck disable=SC2154

deploy_observability_playbook() {
    tags=""
    if [ "${deploy_observability}" = "yes" ]; then
        tags+="deploy_observability,"
    fi
    if [ "${deploy_logging}" = "yes" ]; then
        tags+="deploy_logging,"
    fi
    tags="${tags%,}"

    local playbook_path="playbooks/deploy-observability.yml"
    if [ "$(echo "${kubernetes_platform:-vanilla}" | tr '[:upper:]' '[:lower:]')" = "openshift" ]; then
        playbook_path="playbooks/deploy-observability-openshift.yml"
    fi

    local extra_vars="secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} deploy_observability=${deploy_observability} deploy_logging=${deploy_logging} observability_stack_chart_version=${observability_stack_chart_version} kubernetes_platform=${kubernetes_platform}"

    ansible-playbook -i "${INVENTORY_PATH}" "$playbook_path" --become --become-user=root --extra-vars "$extra_vars" --tags "$tags" --vault-password-file "$vault_pass_file"
}