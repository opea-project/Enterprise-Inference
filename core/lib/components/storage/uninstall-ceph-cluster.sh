# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

uninstall_ceph_cluster() {
    echo "Uninstalling Ceph Cluster..."
    echo "WARNING: This will PERMANENTLY DELETE ALL CEPH DATA!"
    
    # Always attempt to run the uninstall playbook, but handle failures gracefully
    echo "Attempting Ceph cluster uninstall (if installed)..."
    if ansible-playbook -i "${INVENTORY_PATH}" playbooks/uninstall-ceph-storage.yml; then
        echo "Ceph cluster uninstall completed successfully."
    else
        echo "Warning: Ceph cluster uninstall encountered issues or Ceph may not be installed."
        echo "This is expected if no Ceph cluster was deployed."
    fi
        
}