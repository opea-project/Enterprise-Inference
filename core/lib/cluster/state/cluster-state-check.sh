# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

check_cluster_state() {
    echo "Checking the state of the Kubernetes cluster..."
    ansible-playbook -i inventory/mycluster/hosts.yaml --become --become-user=root upgrade-cluster.yml --check
    # Check the exit status of the Ansible playbook command
    if [ $? -eq 0 ]; then
        echo "Kubernetes cluster state check completed successfully."
    else
        echo "Kubernetes cluster state check indicates potential issues."
        return 1 # Return a non-zero value to indicate potential issues
    fi
}

run_k8s_cluster_wait() {
    echo "Waiting for Kubernetes control plane to become ready..."
    ansible -i "${INVENTORY_PATH}" kube_control_plane -m wait_for -a "port=6443 timeout=600" --become --become-user=root   
    return $?
}
