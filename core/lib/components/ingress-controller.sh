# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# shellcheck shell=bash
# This file is a library fragment sourced by core/inference-stack-deploy.sh.
# Configuration globals are defined in lib/system/config-vars.sh and populated by
# lib/system/precheck/read-config-file.sh, and are shared across the sourced fragments.
# shellcheck disable=SC2154

run_ingress_nginx_playbook() {
    echo "Deploying the Ingress NGINX Controller..."
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-ingress-controller.yml --extra-vars "secret_name=${cluster_url} cert_file=${cert_file} key_file=${key_file} ingress_controller=${ingress_controller}"  
}