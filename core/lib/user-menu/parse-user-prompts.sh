# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

parse_arguments() {
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --cluster-url) cluster_url="$2"; shift ;;
            --cert-file) cert_file="$2"; shift ;;
            --key-file) key_file="$2"; shift ;;
            --keycloak-client-id) keycloak_client_id="$2"; shift ;;
            --keycloak-admin-user) keycloak_admin_user="$2"; shift ;;
            --keycloak-admin-password) keycloak_admin_password="$2"; shift ;;
            --hugging-face-token) hugging_face_token="$2"; shift ;;
            --models) models="$2"; shift ;;
            --cpu-or-gpu) cpu_or_gpu="$2"; shift ;;
            --deploy-nri-balloon-policy) deploy_nri_balloon_policy="$2"; shift ;;
            --skip-check) skip_check="true" ;;
            -h|--help) usage; exit 0 ;;
            *) echo "Unknown parameter passed: $1"; exit 1 ;;
        esac
        shift
    done
}


prompt_for_input() {   
    if [ -z "$deploy_kubernetes_fresh" ]; then
        read -p "Do you want to proceed with deploying fresh Kubernetes cluster setup? (yes/no): " deploy_kubernetes_fresh
    else
        echo "Proceeding with the setup of Fresh Kubernetes cluster: $deploy_kubernetes_fresh"
    fi
    if [ -z "$deploy_habana_ai_operator" ]; then
        read -p "Do you want to proceed with deploying Habana AI Operator? (yes/no): " deploy_habana_ai_operator
    else
        echo "Proceeding with the setup of Habana AI Operator: $deploy_habana_ai_operator"
    fi
    if [ -z "$deploy_ingress_controller" ]; then
        read -p "Do you want to proceed with deploying Ingress NGINX Controller? (yes/no): " deploy_ingress_controller
    else
        echo "Proceeding with the setup of Ingress Controller: $deploy_ingress_controller"
    fi
    if [ -z "$deploy_keycloak" ]; then
        read -p "Do you want to proceed with deploying Keycloak & APISIX? (yes/no): " deploy_keycloak
        
    else
        echo "Proceeding with the setup of Keycloak : $deploy_keycloak"
    fi
    if [ -z "$deploy_apisix" ]; then
        read -p "Do you want to proceed with deploying Keycloak & APISIX? (yes/no): " deploy_apisix
        
    else
        echo "Proceeding with the setup of Apisix: $deploy_apisix"
    fi

    if [ -z "$deploy_genai_gateway" ]; then
        read -p "Do you want to proceed with deploying GenAI Gateway? (yes/no): " deploy_genai_gateway
    else
        echo "Proceeding with the setup of GenAI Gateway: $deploy_genai_gateway"
    fi
    
    if [ -z "$deploy_observability" ]; then
        read -p "Do you want to proceed with deploying Observability? (yes/no): " deploy_observability
    else
        echo "Proceeding with the setup of Observability: $deploy_observability"
    fi

    if [ -z "$deploy_ceph" ]; then
        read -p "Do you want to proceed with deploying Ceph cluster setup? (yes/no): " deploy_ceph
    else
        echo "Proceeding with the setup of Ceph cluster: $deploy_ceph"
    fi
    
    if [ "$deploy_kubernetes_fresh" == "no" ]; then
        if [ -z "$uninstall_ceph" ]; then
            read -p "Do you want to proceed with uninstalling Ceph cluster? (yes/no): " uninstall_ceph
        else
            echo "Proceeding with Ceph cluster uninstallation: $uninstall_ceph"
        fi
    fi
           
    if [ -z "$deploy_istio" ]; then
        read -p "Do you want to proceed with deploying Istio? (yes/no): " deploy_istio
    else
        echo "Proceeding with the setup of Istio: $deploy_istio"
    fi

    if [ -z "$deploy_nri_balloon_policy" ]; then
        # Automatically enable NRI balloon policy for CPU deployments
        if [ "$cpu_or_gpu" == "c" ]; then
            deploy_nri_balloon_policy="yes"
            if [ "$balloon_policy_cpu" == "enabled" ]; then
                echo "NRI CPU Balloon Policy automatically enabled for CPU deployment"
            fi            
        else
            deploy_nri_balloon_policy="no"
            echo "NRI CPU Balloon Policy disabled for GPU deployment"
        fi
    else
        echo "Proceeding with the setup of NRI CPU Balloon Policy: $deploy_nri_balloon_policy"
    fi

    model_selection "$@"    
    echo "----- Input -----"
    if [ -z "$cluster_url" ]; then
        read -p "Enter the CLUSTER URL (FQDN): " cluster_url
    else
        echo "Using provided CLUSTER URL: $cluster_url"
    fi
    if [ -z "$cert_file" ]; then
        read -p "Enter the full path to the certificate file: " cert_file
    else
        echo "Using provided certificate file: $cert_file"
    fi    
    if [ -z "$key_file" ]; then
        read -p "Enter the full path to the key file: " key_file
    else
        echo "Using provided key file: $key_file"
    fi
    if [ $deploy_keycloak == "yes" ]; then
        if [ -z "$keycloak_client_id" ]; then
            read -p "Enter the keycloak client id: " keycloak_client_id
        else
            echo "Using provided keycloak client id: $keycloak_client_id"
        fi
        if [ -z "$keycloak_admin_user" ]; then
            read -p "Enter the Keycloak admin username: " keycloak_admin_user
        else
            echo "Using provided Keycloak admin username: $keycloak_admin_user"
        fi
        if [ -z "$keycloak_admin_password" ]; then
            read -sp "Enter the Keycloak admin password: " keycloak_admin_password
            echo
        else
            echo "Using provided Keycloak admin password"
        fi
    fi        
    
    if [[ -z "$cpu_or_gpu" ]]; then
        read -p "Do you want to run on CPU or GPU? (c/g): " cpu_or_gpu
        case "$cpu_or_gpu" in
            c|C)
                cpu_or_gpu="c"
                echo "Running on CPU"
                ;;
            g|G)
                cpu_or_gpu="g"
                echo "Running on GPU"
                ;;
            *)
                echo "Invalid option. Defaulting to CPU."
                cpu_or_gpu="c"
                ;;
        esac
    else
        echo "cpu_or_gpu is already set to $cpu_or_gpu"
    fi
    
}