# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


fresh_installation() {

     if [[ "$brownfield_deployment" == "yes" ]]; then
        echo "Brownfield deployment setup is selected..."
        # TODO: Check existing cluster status
        deploy_kubernetes_fresh="no"
        skip_check="true"
        # Update config file to reflect that Kubernetes deployment is disabled for Brownfield deployment
        sed -i 's/^deploy_kubernetes_fresh=.*/deploy_kubernetes_fresh=off/' "$SCRIPT_DIR/inventory/inference-config.cfg" 2>/dev/null || true
        # Comment out the deploy_kubernetes_fresh line to make it clear it's disabled for Brownfield deployment
        # sed -i 's/^deploy_kubernetes_fresh=/#deploy_kubernetes_fresh=/' "$SCRIPT_DIR/inventory/inference-config.cfg" 2>/dev/null || true
    fi

    read_config_file

    echo "Deployment configuration: $deploy_kubernetes_fresh"

    if [[ "$deploy_kubernetes_fresh" == "no" && "$deploy_habana_ai_operator" == "no" && "$deploy_ingress_controller" == "no" && "$deploy_keycloak" == "no" && "$deploy_apisix" == "no" && "$deploy_llm_models" == "no" && "$deploy_observability" == "no" && "$deploy_genai_gateway" == "no" && "$deploy_istio" == "no" && "$deploy_ceph" == "no" && "$uninstall_ceph" == "no"  && "$deploy_nri_balloon_policy" == "no" ]]; then

    # Check if all deployment steps are set to "no" after getting user input
        echo "No installation or deployment steps selected. Skipping setup_initial_env..."
        echo "--------------------------------------------------------------------"
        echo "|     Deployment Skipped for Intel AI for Enterprise Inference!    |"
        echo "--------------------------------------------------------------------"
    else
        prompt_for_input
        if [[ "$brownfield_deployment" == "yes" ]]; then
            read -p "${YELLOW}ATTENTION: Do you wish to continue with Brownfield Deployment setup? (yes/no) ${NC}" -r proceed_with_installation
        else
            read -p "${YELLOW}ATTENTION: Ensure that the nodes do not contain existing workloads. If necessary, please purge any previous cluster configurations before initiating a fresh installation to avoid an inappropriate cluster state. Proceeding without this precaution could lead to service disruptions or data loss. Do you wish to continue with the setup? (yes/no) ${NC}" -r proceed_with_installation
        fi

        if [[ "$proceed_with_installation" =~ ^([yY][eE][sS]|[yY])+$ ]]; then

            setup_initial_env "$@"

             if [[ "$brownfield_deployment" == "yes" ]]; then
                echo "Setting up Bastion Node..."
                setup_bastion "$@"
                INVENTORY_PATH=$brownfield_deployment_host_file
            fi

            if [[ "$deploy_kubernetes_fresh" == "yes" ]]; then
                echo "Starting fresh installation of Intel AI for Enterprise Inference Cluster..."
                install_kubernetes "$@"
            else
                echo "Skipping Kubernetes installation..."
            fi
            execute_and_check "Deploying Cluster Configuration Playbook..." deploy_cluster_config_playbook \
                  "Cluster Configuration Playbook is deployed successfully." \
                  "Failed to deploy Cluster Configuration Playbook. Exiting."

            # Deploy NRI CPU Balloons for CPU deployments (after all infrastructure, before models)
            if [[ "$deploy_nri_balloon_policy" == "yes" ]]; then
                # Ensure this is a CPU deployment
                if [[ "$cpu_or_gpu" != "c" ]]; then
                    echo "${RED}Error: NRI Balloon Policy can only be deployed for CPU deployments (cpu_or_gpu='c')${NC}"
                    echo "${RED}Current cpu_or_gpu setting: '$cpu_or_gpu'${NC}"
                    echo "${RED}Please set cpu_or_gpu to 'c' or disable NRI balloon policy deployment. Exiting!${NC}"
                    exit 1
                fi
                execute_and_check "Deploying CPU Optimization (NRI Balloons & Topology Detection)..." deploy_nri_balloons_playbook "$@" \
                    "CPU optimization deployed successfully." \
                    "Failed to deploy CPU optimization. Exiting!."
            else
                echo "Skipping CPU optimization deployment..."
            fi
            if [[ "$deploy_habana_ai_operator" == "yes" ]]; then
                execute_and_check "Deploying habana-ai-operator..." run_deploy_habana_ai_operator_playbook "Habana AI Operator is deployed." \
                    "Failed to deploy Habana AI Operator. Exiting."
            else
                echo "Skipping Habana AI Operator installation..."
            fi

            if [[ "$uninstall_ceph" == "yes" ]]; then
                execute_and_check "Uninstalling CEPH storage..." uninstall_ceph_cluster "$@" \
                    "CEPH is uninstalled successfully." \
                    "Failed to uninstall CEPH. Exiting!."
            else
                echo "Skipping CEPH storage uninstallation..."
            fi

            if [[ "$deploy_ceph" == "yes" ]]; then
                execute_and_check "Deploying CEPH storage..." deploy_ceph_cluster "$@" \
                    "CEPH is deployed successfully." \
                    "Failed to deploy CEPH. Please use uninstall_ceph option to clean previous installation and format devices if needed."
            else
                echo "Skipping CEPH storage deployment..."
            fi

            if [[ "$deploy_ingress_controller" == "yes" ]]; then
                execute_and_check "Deploying Ingress NGINX Controller..." run_ingress_nginx_playbook \
                    "Ingress NGINX Controller is deployed successfully." \
                    "Failed to deploy Ingress NGINX Controller. Exiting."
            else
                echo "Skipping Ingress NGINX Controller deployment..."
            fi

            if [[ "$deploy_keycloak" == "yes" || "$deploy_apisix" == "yes" ]]; then
                execute_and_check "Deploying Keycloak..." run_keycloak_playbook \
                    "Keycloak is deployed successfully." \
                    "Failed to deploy Keycloak. Exiting."
                execute_and_check "Deploying Keycloak TLS secret..." create_keycloak_tls_secret_playbook "$@" \
                    "Keycloak TLS secret is deployed successfully." \
                    "Failed to deploy Keycloak TLS secret. Exiting."
            else
                echo "Skipping Keycloak deployment..."
            fi
            if [[ "$deploy_genai_gateway" == "yes" ]]; then
                echo "successfully deploying genai gateway"
                execute_and_check "Deploying GenAI Gateway..." run_genai_gateway_playbook \
                    "GenAI Gateway is deployed successfully." \
                    "Failed to deploy GenAI Gateway. Exiting."
            else
                echo "Skipping GenAI Gateway deployment..."
            fi

            if [[ "$deploy_observability" == "yes" ]]; then
                echo "Deploying observability..."
                execute_and_check "Deploying Observability..." deploy_observability_playbook "$@" \
                    "Observability is deployed successfully." \
                    "Failed to deploy Observability. Exiting!."
            else
                echo "Skipping Observability deployment..."
            fi
            if [[ "$deploy_istio" == "yes" ]]; then
                echo "Deploying Istio..."
                execute_and_check "Deploying Istio..." deploy_istio_playbook "$@" \
                    "Istio is deployed successfully." \
                    "Failed to deploy Istio. Exiting!."
            else
                echo "Skipping Istio deployment..."
            fi


            if [[ "$deploy_llm_models" == "yes" ]]; then
                model_name_list=$(get_model_names)
                if [ -z "$model_name_list" ]; then
                    echo "No models provided. Exiting..."
                    exit 1
                    fi
                execute_and_check "Deploying Inference LLM Models..." deploy_inference_llm_models_playbook "$@" \
                    "Inference LLM Model is deployed successfully." \
                    "Failed to deploy Inference LLM Model Exiting!."
            else
                echo "Skipping LLM Model deployment..."
            fi



            if [ "$deploy_llm_models" == "yes" ]; then
            echo -e "${BLUE}-------------------------------------------------------------------------------------${NC}"
            echo -e "${GREEN}|  AI LLM Model Deployment Complete!                                                |${NC}"
            echo -e "${GREEN}|  The model is transitioning to a state ready for Inference.                       |${NC}"
            echo -e "${GREEN}|  This may take some time depending on system resources and other factors.         |${NC}"
            echo -e "${GREEN}|  Please standby...                                                                |${NC}"
            echo -e "${BLUE}--------------------------------------------------------------------------------------${NC}"
            echo ""
            echo "Accessing Deployed Models for Inference"
            echo "https://github.com/opea-project/Enterprise-Inference/blob/main/docs/accessing-deployed-models.md"
            echo ""
            echo "Please refer to this comprehensive guide for detailed instructions."
            echo ""
            else
            echo -e "${BLUE}-------------------------------------------------------------------------------------${NC}"
            echo -e "${GREEN}|  AI Inference Deployment Complete!                                                |${NC}"
            echo -e "${GREEN}|  Resources are transitioning to a state ready for Inference.                      |${NC}"
            echo -e "${GREEN}|  This may take some time depending on system resources and other factors.         |${NC}"
            echo -e "${GREEN}|  Please standby...                                                                |${NC}"
            echo -e "${BLUE}--------------------------------------------------------------------------------------${NC}"
            echo ""
            echo "Accessing Deployed Resources for Inference"
            echo "https://github.com/opea-project/Enterprise-Inference/blob/main/docs/accessing-deployed-models.md"
            echo ""
            echo "Please refer to this comprehensive guide for detailed instructions."
            echo ""
            fi
        else
            echo "-------------------------------------------------------------------"
            echo "|     Deployment Skipped for Intel AI for Enterprise Inference!    |"
            echo "--------------------------------------------------------------------"
        fi
    fi
}


run_fresh_install_playbook() {
    echo "Running the cluster.yml playbook to set up the Kubernetes cluster..."
    ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root cluster.yml
}