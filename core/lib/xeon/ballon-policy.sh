# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

deploy_nri_balloons_playbook() {
    if [ "$balloon_policy_cpu" = "enabled" ]; then
        echo "Deploying CPU Optimization (NRI Balloons & Topology Detection)..."    
        # Strict CPU deployment check
        if [[ "$cpu_or_gpu" != "c" ]]; then
            echo "${RED}Error: CPU optimization can only be deployed for CPU deployments${NC}"
            echo "${RED}Current cpu_or_gpu setting: '$cpu_or_gpu'${NC}"
            echo "${RED}CPU optimization is specifically designed for CPU resource management${NC}"
            exit 1
        fi
        
        if [ "$deploy_nri_balloon_policy" == "yes" ] || [ "$cpu_or_gpu" == "c" ]; then
            echo "${GREEN}Deploying CPU optimization with topology detection and NRI balloon policy${NC}"
            ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-cpu-optimization.yml \
                --extra-vars "cpu_playbook=true" \
                --extra-vars "kubernetes_platform=${kubernetes_platform}"
            if [ $? -eq 0 ]; then
                echo "${GREEN}CPU optimization deployed successfully${NC}"
            else
                echo "${RED}CPU optimization deployment failed${NC}"
                exit 1
            fi
        else
            echo "${YELLOW}Skipping CPU optimization - not a CPU deployment${NC}"
        fi
    fi
}