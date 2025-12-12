# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

deploy_istio_playbook() {
    echo "Deploying Istio service mesh..."
    if [ "$deploy_istio" != "yes" ]; then
        echo "Skipping Istio deployment as deploy_istio is set to '$deploy_istio'."
        return 0
    fi

    # Expect kubernetes_platform to be set globally (brownfield or fresh install path)
    if [ "$(echo "${kubernetes_platform:-vanilla}" | tr '[:upper:]' '[:lower:]')" = "openshift" ]; then
        echo "Detected OpenShift platform. Using OpenShift Service Mesh playbook."
        ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-istio-openshift.yml --extra-vars "kubernetes_platform=${kubernetes_platform}" || return 1
    else
        echo "Using vanilla/helm-based Istio playbook for platform: ${kubernetes_platform}"
        ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-istio.yml --extra-vars "kubernetes_platform=${kubernetes_platform}" || return 1
    fi
}