manage_kubeconfig() {
    local max_attempts=3
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        # Prompt for kubeconfig file path
        if [ -z "$kubeconfig_file" ] || [ $attempt -gt 1 ]; then
            echo "Attempt $attempt of $max_attempts:"
            read -p "Enter the full path to the kubeconfig file to provision brownfield deployment: " kubeconfig_file
        else
            echo "Using provided kubeconfig file: $kubeconfig_file"
        fi

        # Check if user wants to exit
        if [ "$kubeconfig_file" = "exit" ] || [ "$kubeconfig_file" = "quit" ]; then
            echo "Exiting brownfield deployment setup."
            return 1
        fi

        # Expand tilde (~) to home directory if present
        kubeconfig_file="${kubeconfig_file/#\~/$HOME}"

        # Validate kubeconfig file exists
        if [ ! -f "$kubeconfig_file" ]; then
            echo "Error: Kubeconfig file '$kubeconfig_file' not found."
            if [ $attempt -eq $max_attempts ]; then
                echo "Maximum attempts reached. Exiting brownfield deployment setup."
                echo "Please ensure the kubeconfig file exists and try again."
                return 1
            else
                echo "Please check the path and try again (or type 'exit' to quit)."
                kubeconfig_file=""  # Reset for next attempt
            fi
            attempt=$((attempt + 1))
        else
            break  # File found, exit the loop
        fi
    done

    # Create .kube directory if it doesn't exist
    mkdir -p ~/.kube

    # Copy kubeconfig to standard location
    cp "$kubeconfig_file" ~/.kube/config
    chmod 600 ~/.kube/config
    #echo "Kubeconfig copied to ~/.kube/config"

    # Export KUBECONFIG for immediate use and future compatibility
    export KUBECONFIG="$HOME/.kube/config"
    #echo "Using kubeconfig: $kubeconfig_file (copied to ~/.kube/config)"
}

prompt_kubernetes_platform() {
    echo ""
    echo "==================================================="
    echo "  Please select your Kubernetes platform:"
    echo "==================================================="
    echo "1) OpenShift/OKD"
    echo "2) Amazon EKS"
    echo "3) Google GKE"
    echo "4) Azure AKS"
    echo "5) Vanilla Kubernetes"
    echo "==================================================="
    read -p "Enter your choice (1-5): " platform_choice
    
    case "$platform_choice" in
        1)
            kubernetes_platform="openshift"
            echo "Selected platform: OpenShift/OKD"
            ;;
        2)
            kubernetes_platform="eks"
            echo "Selected platform: Amazon EKS"
            ;;
        3)
            kubernetes_platform="gke"
            echo "Selected platform: Google GKE"
            ;;
        4)
            kubernetes_platform="aks"
            echo "Selected platform: Azure AKS"
            ;;
        5)
            kubernetes_platform="vanilla"
            echo "Selected platform: Vanilla Kubernetes"
            ;;
        *)
            echo "Invalid choice. Defaulting to Vanilla Kubernetes."
            kubernetes_platform="vanilla"
            ;;
    esac
    
    echo "Setting kubernetes_platform=${kubernetes_platform}"
}

detect_kubernetes_platform() {
    echo "Detecting Kubernetes platform..."
    
    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        echo "Warning: kubectl not found in PATH. Platform detection skipped."
        echo "Please ensure kubectl is installed and in your PATH."
        prompt_kubernetes_platform
        return 1
    fi
    
    local platform=$(kubectl version --request-timeout=5s -o json 2>/dev/null | {
        if kubectl api-resources --api-group=route.openshift.io --request-timeout=5s 2>/dev/null | grep -q '^routes'; then
            echo "openshift"
        elif kubectl version --request-timeout=5s -o json 2>/dev/null | grep -qi "eks"; then
            echo "eks"
        elif kubectl get nodes -o jsonpath='{.items[0].status.nodeInfo.osImage}' --request-timeout=5s 2>/dev/null | grep -qi "bottlerocket"; then
            echo "eks"
        elif kubectl get nodes -o jsonpath='{.items[0].status.nodeInfo.osImage}' --request-timeout=5s 2>/dev/null | grep -qi "amazon"; then
            echo "eks"
        elif kubectl version --request-timeout=5s -o json 2>/dev/null | grep -qi "gke"; then
            echo "gke"
        elif kubectl version --request-timeout=5s -o json 2>/dev/null | grep -qi "aks"; then
            echo "aks"
        elif kubectl version --request-timeout=5s -o json 2>/dev/null | jq -r '.serverVersion.gitVersion' 2>/dev/null | grep -qE '^v[0-9]+\.[0-9]+\.[0-9]+$' && \
             ! kubectl version --request-timeout=5s -o json 2>/dev/null | grep -qiE '(eks|gke|aks|openshift)'; then
            echo "vanilla"
        else
            echo "unknown"
        fi
    })
    
    if [ -z "$platform" ] || [ "$platform" = "unknown" ]; then
        echo "Warning: Unable to detect Kubernetes platform automatically."
        prompt_kubernetes_platform
        return 0
    fi
    
    # Map platform to kubernetes_platform variable for Ansible
    case "$platform" in
        openshift)
            kubernetes_platform="openshift"
            echo "Detected platform: OpenShift/OKD"
            ;;
        eks)
            kubernetes_platform="eks"
            echo "Detected platform: Amazon EKS"
            ;;
        gke)
            kubernetes_platform="gke"
            echo "Detected platform: Google GKE"
            ;;
        aks)
            kubernetes_platform="aks"
            echo "Detected platform: Azure AKS"
            ;;
        vanilla)
            kubernetes_platform="vanilla"
            echo "Detected platform: Vanilla Kubernetes"
            ;;
        *)
            kubernetes_platform="vanilla"
            echo "Detected platform: Unknown (defaulting to Vanilla Kubernetes)"
            ;;
    esac
    
    # Set for use in Ansible playbooks
    echo "Setting kubernetes_platform=${kubernetes_platform}"
    return 0
}

brownfield_deployment() {
    if ! manage_kubeconfig; then
        echo "Failed to configure kubeconfig. Returning to main menu."
        return 1
    fi
    
    # Detect Kubernetes platform
    if ! detect_kubernetes_platform; then
        echo "Warning: Platform detection failed. Continuing with default settings."
    fi
    
    echo "-------------------------------------------------"
    echo "|     Brownfield Deployment Operations               |"
    echo "|------------------------------------------------|"
    echo "| 1) Deploy Inference Stack                      |"
    echo "| 2) Manage Models                               |"
    echo "|------------------------------------------------|"
    echo "Please choose an option (1 or 2):"
    read -p "> " brownfield_choice
    case $brownfield_choice in
        1)
            brownfield_deployment="yes"
            deploy_ceph="no"
            uninstall_ceph="no"
            fresh_installation "$@"
            ;;
        2)
            brownfield_deployment="yes"
            manage_models "$@"
            ;;
        *)
            echo "Invalid option. Please enter 1 or 2."
            brownfield_deployment "$@"
            ;;
    esac
}

run_setup_bastion_playbook() {
    echo "Running the setup-bastion.yml playbook to set up the bastion host..."

    # Auto-generate hosts.yaml for brownfield deployment bastion setup
    cat > "$brownfield_deployment_host_file" << EOF
all:
  hosts:
    localhost:
      ansible_connection: local
      ansible_user: $(whoami)
  children:
    kube_control_plane:
      hosts:
        localhost:
EOF
    echo "Generated bastion hosts file for brownfield deployment at: $brownfield_deployment_host_file"
    ansible-playbook -i "$brownfield_deployment_host_file" playbooks/setup-bastion.yml
}


setup_bastion() {

    execute_and_check "Starting Bastion node setup ..." run_setup_bastion_playbook \
        "Bastion node is set up." \
        "Bastion node setup failed. Exiting."
}