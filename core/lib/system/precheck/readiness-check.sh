# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_infrastructure_readiness_check() {
    echo "Running infrastructure readiness check..."
    echo "This will verify system compatibility and infrastructure requirements."
        
    if [ ! -f "$HOMEDIR/inventory/hosts.yaml" ]; then
        echo -e "${RED}Error: Inventory file not found at $HOMEDIR/inventory/hosts.yaml${NC}"
        echo -e "${YELLOW}Please ensure the inventory file exists and contains the correct host information.${NC}"
        return 1
    fi    
    if ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root --extra-vars "brownfield_deployment=true" playbooks/inference-precheck.yml; then
        echo -e "${GREEN}Infrastructure readiness check completed successfully.${NC}"
        return 0
    else
        echo -e "${RED}Infrastructure readiness check failed. Please resolve the issues before proceeding.${NC}"
        return 1
    fi
}