# Copyright (C) 2025-2026 Intel Corporation
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

    if [[ "$deploy_kubernetes_fresh" == "no" && "$deploy_habana_ai_operator" == "no" && "$deploy_ingress_controller" == "no" && "$deploy_keycloak" == "no" && "$deploy_apisix" == "no" && "$deploy_llm_models" == "no" && "$deploy_observability" == "no" && "$deploy_genai_gateway" == "no" && "$deploy_istio" == "no" && "$deploy_ceph" == "no" && "$uninstall_ceph" == "no"  && "$deploy_nri_balloon_policy" == "no" && "$deploy_agenticai_plugin" == "no" && "$deploy_finetune_plugin" == "no" ]]; then

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
                if [[ "$airgap_enabled" == "yes" ]]; then
                    echo "Airgap mode: fixing containerd mirrors and purging any stale image blobs before Kubernetes install..."
                    local _b64 _jfrog_host
                    _jfrog_host=$(echo "$jfrog_url" | sed 's|https\?://||' | sed 's|/.*||')
                    _b64=$(echo -n "${jfrog_username}:${jfrog_password}" | base64 -w 0)
                    for _reg in docker.io ghcr.io registry.k8s.io quay.io public.ecr.aws; do
                        sudo mkdir -p /etc/containerd/certs.d/$_reg
                        sudo tee /etc/containerd/certs.d/$_reg/hosts.toml > /dev/null <<EOF
server = "https://$_reg"
[host."http://${_jfrog_host}/v2/ei-docker-virtual"]
  capabilities = ["pull", "resolve"]
  override_path = true
  [host."http://${_jfrog_host}/v2/ei-docker-virtual".header]
    Authorization = ["Basic $_b64"]
EOF
                    done
                    # Purge any HTML blobs cached from failed prior pulls (containerd corruption loop)
                    for _img in docker.io/library/nginx:1.25.2-alpine; do
                        sudo crictl rmi "$_img" 2>/dev/null; true
                        sudo ctr -n k8s.io images rm "$_img" 2>/dev/null; true
                    done
                    sudo find /var/lib/containerd/io.containerd.content.v1.content/blobs/sha256 \
                        -size +100k -newer /etc/containerd/config.toml \
                        -exec sh -c 'file "$1" | grep -q "HTML" && sudo rm -f "$1"' _ {} \; 2>/dev/null; true
                    sudo systemctl restart containerd
                    echo "Containerd mirrors configured and restarted."
                fi
                install_kubernetes "$@"
                if [[ "$airgap_enabled" == "yes" ]]; then
                    echo "Patching local-path-config to use busybox:1.28 (airgap mode)..."
                    kubectl patch configmap local-path-config -n local-path-storage --type merge -p \
                      '{"data":{"helperPod.yaml":"apiVersion: v1\nkind: Pod\nmetadata:\n  name: helper-pod\nspec:\n  containers:\n  - name: helper-pod\n    image: \"docker.io/library/busybox:1.28\"\n    imagePullPolicy: IfNotPresent"}}' \
                      2>/dev/null || true
                fi
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
            # Deploy Plugins
            # --------------
            # Plugins are deployed after core infrastructure is ready
            
            if [[ "$deploy_agenticai_plugin" == "yes" ]]; then
                echo "Deploying Agentic AI Plugin..."
                ansible-playbook -i "${INVENTORY_PATH}" ../../plugins/agenticai/playbooks/deploy-agenticai-plugin.yml \
                    --extra-vars "cluster_url=${cluster_url} \
                                  cert_file=${cert_file} \
                                  key_file=${key_file} \
                                  kubernetes_platform=${kubernetes_platform} \
                                  airgap_enabled=${airgap_enabled} \
                                  jfrog_url=${jfrog_url} \
                                  jfrog_username=${jfrog_username} \
                                  jfrog_password=${jfrog_password}" \
                    --vault-password-file "$vault_pass_file"
                if [ $? -eq 0 ]; then
                    echo "Agentic AI Plugin deployed successfully."
                else
                    echo "Failed to deploy Agentic AI Plugin. Exiting!."
                    exit 1
                fi
            else
                echo "Skipping Agentic AI Plugin deployment..."
            fi

            if [[ "$deploy_finetune_plugin" == "yes" ]]; then
                echo "Deploying Fine-Tuning Plugin..."
                ansible-playbook -i "${INVENTORY_PATH}" ../../blueprints/finetuning_service/playbooks/deploy-all.yml \
                    --extra-vars "cluster_url=${cluster_url} \
                                  cert_file=${cert_file} \
                                  key_file=${key_file} \
                                  kubernetes_platform=${kubernetes_platform}" \
                    --vault-password-file "$vault_pass_file"
                if [ $? -eq 0 ]; then
                    echo "Fine-Tuning Plugin deployed successfully."
                else
                    echo "Failed to deploy Fine-Tuning Plugin. Exiting!."
                    exit 1
                fi
            else
                echo "Skipping Fine-Tuning Plugin deployment..."
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
    local _airgap_extra_vars=""
    if [[ "$airgap_enabled" == "yes" ]]; then
        _airgap_extra_vars="--extra-vars \"airgap_enabled=true jfrog_username=${jfrog_username} jfrog_password=${jfrog_password}\""
    fi
    eval ansible-playbook -i "${INVENTORY_PATH}" --become --become-user=root cluster.yml ${_airgap_extra_vars}
}