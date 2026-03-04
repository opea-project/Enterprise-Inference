# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

deploy_ceph_cluster() {

    echo "Deploying Ceph Cluster..."

    echo "Generating Ceph configuration values..."
    if ! ansible-playbook -i "${INVENTORY_PATH}" playbooks/generate-ceph-values.yml; then
        echo -e "${RED}Failed to generate Ceph configuration values.${NC}"
        echo -e "${YELLOW}Please check the inventory configuration and try again.${NC}"
        return 1
    fi

    echo "Deploying Ceph storage cluster..."
    if ! ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-ceph-storage.yml; then
        echo -e "${RED} Ceph Cluster deployment FAILED!${NC}"
        echo ""
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}│                        CEPH DEPLOYMENT FAILURE                           │${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}│  Common causes and solutions:                                            │${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}│  1. Previous Ceph installation exists:                                   │${NC}"
        echo -e "${YELLOW}│     • Run this script with 'uninstall_ceph=on' in config                 │${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}│  2. Storage devices need formatting:                                     │${NC}"
        echo -e "${YELLOW}│     • Check available devices                                            │${NC}"
        echo -e "${YELLOW}│     • Format devices if needed                                           │${NC}"
        echo -e "${YELLOW}│     • Remove any existing partitions                                     │${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}│  3. Insufficient resources:                                              │${NC}"
        echo -e "${YELLOW}│     • Ensure nodes have enough CPU, memory, and storage                  │${NC}"
        echo -e "${YELLOW}│     • Check node readiness: kubectl get nodes                            │${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}│  4. Network/connectivity issues:                                         │${NC}"
        echo -e "${YELLOW}│     • Verify all nodes can communicate                                   │${NC}"
        echo -e "${YELLOW}│     • Check firewall rules and port accessibility                        │${NC}"
        echo -e "${YELLOW}│                                                                          │${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}│                                                                                 │${NC}"
        echo -e "${YELLOW}│  RECOMMENDED ACTIONS:                                                           │${NC}"
        echo -e "${YELLOW}│                                                                                 │${NC}"
        echo -e "${YELLOW}│  1. Clean up any previous Ceph installation:                                    │${NC}"
        echo -e "${YELLOW}│     • Set 'uninstall_ceph=on' in inference-config.cfg                           │${NC}"
        echo -e "${YELLOW}│     • Run the deployment script again                                           │${NC}"
        echo -e "${YELLOW}│                                                                                 │${NC}"
        echo -e "${YELLOW}│  2. Format storage devices if required:                                         │${NC}"
        echo -e "${YELLOW}│     • sudo wipefs -a /dev/<device> (replace <device> with your storage device)  │${NC}"
        echo -e "${YELLOW}│     • sudo sgdisk --zap-all /dev/<device>                                       │${NC}"
        echo -e "${YELLOW}│     • sudo dd if=/dev/<device> of=/dev/<device> bs=1M status=progress           │${NC}"
        echo -e "${YELLOW}│                                                                                 │${NC}"
        echo -e "${YELLOW}│  3. Verify system requirements and try again                                    │${NC}"
        echo -e "${YELLOW}│                                                                                 │${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "${RED}Ceph deployment failed. Please address the issues above and retry.${NC}"
        return 1
    fi

    echo -e "${GREEN} Ceph Cluster deployed successfully!${NC}"
    return 0
        
}