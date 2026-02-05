#!/bin/bash
#
# Combined Enterprise Inference Stack Deployment Script
# This script combines genai-system-setup.sh, genai-owner-setup.sh, and post-os-setup.sh
# with resume capability to continue from where it failed.
#
# Usage:
#   ./deploy-enterprise-inference.sh -u <username> -t <huggingface_token> [OPTIONS]
#   ./deploy-enterprise-inference.sh uninstall -u <username> [OPTIONS]
#
# Options:
#   -u, --username          Enterprise Inference owner username (required)
#   -t, --token            Hugging Face token (required)
#   -p, --password         User sudo password for Ansible (default: Linux123!)
#   -g, --gpu-type         GPU type: 'gaudi3' or 'cpu' (default: gaudi3)
#   -m, --models           Model IDs to deploy, comma-separated (default: "5")
#   -b, --branch            Git branch to clone (default: dell-deploy)
#   -f, --firmware-version Firmware version (default: 1.22.1)
#   -d, --deployment-mode  Deployment mode: 'keycloak' or 'genai' (default: keycloak)
#   -o, --observability    Enable observability: 'on' or 'off' (default: off)
#   -r, --resume            Resume from checkpoint (auto-detected if state file exists)
#   -s, --state-file        State file path (default: /tmp/ei-deploy.state)
#   -h, --help              Show this help message
#
# Example:
#   ./deploy-enterprise-inference.sh -u user -t hf_xxxxxxxxxxxxx -g gaudi3 -m "5"
#   ./deploy-enterprise-inference.sh -u user -t hf_xxxxxxxxxxxxx -g cpu -m "1" -d genai -o on
#   ./deploy-enterprise-inference.sh uninstall -u user

set -euo pipefail

# Default values
USERNAME="Replace-with-your-username"
HF_TOKEN="Replace-with-your-hugging face token"
USER_PASSWORD="Replace-with-your-user-password"
GPU_TYPE="Enter gaudi3/cpu based on your deployment"
MODELS="Enter Model number"
DEPLOYMENT_MODE="keycloak"
DEPLOY_OBSERVABILITY="off"
KEYCLOAK_CLIENT_ID="api"
KEYCLOAK_ADMIN_USER="api-admin"
KEYCLOAK_ADMIN_PASSWORD="changeme!!"
FIRMWARE_VERSION="1.22.1"
STATE_FILE="/tmp/ei-deploy.state"
BRANCH="release-1.4.0"
REPO_URL="https://github.com/opea-project/Enterprise-Inference"
RESUME=false
ACTION="deploy"

# Model ID mapping (numeric selector -> Hugging Face model id)
declare -A MODEL_MAP=(
    ["1"]="meta-llama/Llama-3.1-8B-Instruct"
    ["2"]="meta-llama/Llama-3.1-70B-Instruct"
    ["3"]="meta-llama/Llama-3.1-405B-Instruct"
    ["4"]="meta-llama/Llama-3.3-70B-Instruct"
    ["5"]="meta-llama/Llama-4-Scout-17B-16E-Instruct"
    ["6"]="Qwen/Qwen2.5-32B-Instruct"
    ["7"]="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
    ["8"]="deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
    ["9"]="mistralai/Mixtral-8x7B-Instruct-v0.1"
    ["10"]="mistralai/Mistral-7B-Instruct-v0.3"
    ["11"]="BAAI/bge-base-en-v1.5"
    ["12"]="BAAI/bge-reranker-base"
    ["13"]="codellama/CodeLlama-34b-Instruct-hf"
    ["14"]="tiiuae/Falcon3-7B-Instruct"
    ["21"]="meta-llama/Llama-3.1-8B-Instruct"
    ["22"]="meta-llama/Llama-3.2-3B-Instruct"
    ["23"]="deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
    ["24"]="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
    ["25"]="Qwen/Qwen3-1.7B"
    ["26"]="Qwen/Qwen3-4B-Instruct-2507"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Hugging Face token checks for selected model numbers
check_hf_token_access() {
    log_info "Validating Hugging Face token..."
    local response http_code body
    response=$(curl -sS -w $'\n%{http_code}' \
        -H "Authorization: Bearer ${HF_TOKEN}" \
        "https://huggingface.co/api/whoami-v2")
    http_code="${response##*$'\n'}"
    body="${response%$'\n'*}"
    if [[ "$http_code" != "200" ]]; then
        log_error "Hugging Face token validation failed (HTTP ${http_code})"
        echo "$body"
        exit 1
    fi
    log_success "Hugging Face token is valid"

    if [[ -z "${MODELS:-}" ]]; then
        log_warn "No model numbers provided; skipping model access checks"
        return 0
    fi

    IFS=',' read -r -a model_numbers <<< "${MODELS}"
    local model_ids=()
    for num in "${model_numbers[@]}"; do
        num="$(echo "$num" | xargs)"
        if [[ -z "$num" ]]; then
            continue
        fi
        if [[ -z "${MODEL_MAP[$num]:-}" ]]; then
            log_warn "Unknown model number '${num}' (no mapping found)"
            continue
        fi
        model_ids+=("${MODEL_MAP[$num]}")
    done

    if [[ ${#model_ids[@]} -eq 0 ]]; then
        log_warn "No valid model numbers found; skipping model access checks"
        return 0
    fi

    log_info "Checking model access for selected numbers..."
    local seen_ids=()
    for model_id in "${model_ids[@]}"; do
        if [[ " ${seen_ids[*]} " == *" ${model_id} "* ]]; then
            continue
        fi
        seen_ids+=("${model_id}")
        log_info "Model: ${model_id}"
        local model_code
        model_code=$(curl -sS -o /dev/null -w "%{http_code}" \
            -H "Authorization: Bearer ${HF_TOKEN}" \
            "https://huggingface.co/api/models/${model_id}")
        if [[ "$model_code" == "200" ]]; then
            log_success "Access confirmed for ${model_id}"
            continue
        fi
        if [[ "$model_code" == "401" || "$model_code" == "403" ]]; then
            log_error "Model is gated or token lacks access: ${model_id} (HTTP ${model_code})"
            exit 1
        fi
        log_error "Unable to access model '${model_id}' (HTTP ${model_code})"
        exit 1
    done
}

update_inference_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        sed -i -E \
            -e 's/^[[:space:]]*hugging_face_token[[:space:]]*=.*/hugging_face_token='${HF_TOKEN}'/' \
            -e 's/^[[:space:]]*models[[:space:]]*=.*/models='${MODELS}'/' \
            -e 's/^[[:space:]]*cpu_or_gpu[[:space:]]*=.*/cpu_or_gpu='${GPU_TYPE}'/' \
            -e 's/^[[:space:]]*keycloak_client_id[[:space:]]*=.*/keycloak_client_id='${KEYCLOAK_CLIENT_ID}'/' \
            -e 's/^[[:space:]]*keycloak_admin_user[[:space:]]*=.*/keycloak_admin_user='${KEYCLOAK_ADMIN_USER}'/' \
            -e 's/^[[:space:]]*keycloak_admin_password[[:space:]]*=.*/keycloak_admin_password='${KEYCLOAK_ADMIN_PASSWORD}'/' \
            -e 's/^[[:space:]]*deploy_keycloak_apisix[[:space:]]*=.*/deploy_keycloak_apisix='${DEPLOY_KEYCLOAK_APISIX}'/' \
            -e 's/^[[:space:]]*deploy_genai_gateway[[:space:]]*=.*/deploy_genai_gateway='${DEPLOY_GENAI_GATEWAY}'/' \
            -e 's/^[[:space:]]*deploy_observability[[:space:]]*=.*/deploy_observability='${DEPLOY_OBSERVABILITY}'/' \
            "$CONFIG_FILE"
        log_info "Updated inference-config.cfg with models='${MODELS}' and cpu_or_gpu=${GPU_TYPE}"
    else
        log_warn "inference-config.cfg not found at $CONFIG_FILE, skipping update."
    fi
}

# Usage function
usage() {
    cat << EOF
Usage: $0 -u <username> -t <huggingface_token> [OPTIONS]
       $0 uninstall -u <username> [OPTIONS]

Required Options (deploy):
  -u, --username          Enterprise Inference owner username
  -t, --token            Hugging Face token

Required Options (uninstall):
  -u, --username          Enterprise Inference owner username

Optional Options:
  -p, --password         User sudo password for Ansible (default: Linux123!)
  -g, --gpu-type         GPU type: 'gaudi3' or 'cpu' (default: gaudi3)
  -m, --models           Model IDs to deploy, comma-separated (default: "1")
  -b, --branch            Git branch to clone (default: dell-deploy)
  -f, --firmware-version Firmware version (default: 1.22.1)
  -d, --deployment-mode  Deployment mode: 'keycloak' or 'genai' (default: keycloak)
  -o, --observability    Enable observability: 'on' or 'off' (default: off)
  -s, --state-file        State file path (default: /tmp/ei-deploy.state)
  -r, --resume            Force resume from checkpoint
  -h, --help              Show this help message

Notes:
  Model numbers map to Hugging Face model IDs defined in MODEL_MAP.

Example:
  $0 -u user -t hf_xxxxxxxxxxxxx -g gaudi3 -m "1"
  $0 -u user -t hf_xxxxxxxxxxxxx -g cpu -m "1" -d genai -o on
  $0 uninstall -u user
EOF
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        uninstall)
            ACTION="uninstall"
            shift
            ;;
        -u|--username)
            USERNAME="$2"
            shift 2
            ;;
        -t|--token)
            HF_TOKEN="$2"
            shift 2
            ;;
        -p|--password)
            USER_PASSWORD="$2"
            shift 2
            ;;
        -g|--gpu-type)
            GPU_TYPE="$2"
            shift 2
            ;;
        -m|--models)
            MODELS="$2"
            shift 2
            ;;
        -b|--branch)
            BRANCH="$2"
            shift 2
            ;;
        -f|--firmware-version)
            FIRMWARE_VERSION="$2"
            shift 2
            ;;
        -d|--deployment-mode)
            DEPLOYMENT_MODE="$2"
            shift 2
            ;;
        -o|--observability)
            DEPLOY_OBSERVABILITY="$2"
            shift 2
            ;;
        -s|--state-file)
            STATE_FILE="$2"
            shift 2
            ;;
        -r|--resume)
            RESUME=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required parameters
if [[ -z "$USERNAME" ]]; then
    log_error "Username is required"
    usage
fi
if [[ "$ACTION" == "deploy" ]] && [[ -z "$HF_TOKEN" ]]; then
    log_error "Hugging Face token is required for deployment"
    usage
fi

# Validate GPU type (deploy only)
if [[ "$ACTION" == "deploy" ]]; then
    if [[ "$GPU_TYPE" != "gaudi3" ]] && [[ "$GPU_TYPE" != "cpu" ]]; then
        log_error "GPU type must be 'gaudi3' or 'cpu'"
        exit 1
    fi
fi

# Validate deployment mode
if [[ "$DEPLOYMENT_MODE" != "keycloak" ]] && [[ "$DEPLOYMENT_MODE" != "genai" ]]; then
    log_error "Deployment mode must be 'keycloak' or 'genai'"
    exit 1
fi

# Validate observability setting
if [[ "$DEPLOY_OBSERVABILITY" != "on" ]] && [[ "$DEPLOY_OBSERVABILITY" != "off" ]]; then
    log_error "Observability must be 'on' or 'off'"
    exit 1
fi
# Set deployment variables based on deployment mode
set_deployment_variables() {
    case "$DEPLOYMENT_MODE" in
        keycloak)
            DEPLOY_KEYCLOAK_APISIX="on"
            DEPLOY_GENAI_GATEWAY="off"
            ;;
        genai)
            DEPLOY_KEYCLOAK_APISIX="off"
            DEPLOY_GENAI_GATEWAY="on"
            ;;
    esac
}

# Initialize deployment variables
set_deployment_variables

# Check if running with root/sudo privileges
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run with sudo/root privileges"
    log_error "Please run: sudo $0 $*"
    exit 1
fi

INVOKING_USER="${SUDO_USER:-$(whoami)}"

# never allow root deployment
if [[ "$INVOKING_USER" == "root" ]]; then
    log_error "Refusing to deploy as root"
    exit 1
fi

# If USERNAME was passed, it must match invoking user
if [[ -n "${USERNAME:-}" && "$USERNAME" != "$INVOKING_USER" ]]; then
    log_error "Username mismatch detected"
    log_error "Invoking user : $INVOKING_USER"
    log_error "Provided user : $USERNAME"
    log_error "Deployment user must match the invoking user"
    exit 1
fi

# Final deployment user (single source of truth)
USERNAME="$INVOKING_USER"

log_info "Deployment user validated: $USERNAME"

# Check if state file exists (for resume)
if [[ -f "$STATE_FILE" ]] || [[ "$RESUME" == true ]]; then
    if [[ -f "$STATE_FILE" ]]; then
        log_info "State file found. Resuming from checkpoint..."
        source "$STATE_FILE"
        RESUME=true
        set_deployment_variables
    else
        log_warn "Resume requested but no state file found. Starting fresh."
        RESUME=false
    fi
else
    RESUME=false
fi

FORCE_INTERACTIVE_DEPLOY=false
if [[ "$RESUME" == true ]] && [[ "${LAST_COMPLETED_STEP:-}" == "deploy_stack" ]]; then
    log_info "Previous deployment detected in state file; skipping setup steps"
    LAST_COMPLETED_STEP="certificates"
    FORCE_INTERACTIVE_DEPLOY=true
fi

# State management functions
save_state() {
    local step=$1
    cat > "$STATE_FILE" << EOF
# Enterprise Inference Deployment State
# Do not edit this file manually
LAST_COMPLETED_STEP="$step"
USERNAME="$USERNAME"
HF_TOKEN="$HF_TOKEN"
USER_PASSWORD="$USER_PASSWORD"
GPU_TYPE="$GPU_TYPE"
MODELS="$MODELS"
BRANCH="$BRANCH"
DEPLOYMENT_MODE="$DEPLOYMENT_MODE"
REPO_URL="$REPO_URL"
FIRMWARE_VERSION="$FIRMWARE_VERSION"
DEPLOY_OBSERVABILITY="$DEPLOY_OBSERVABILITY"
EOF
    log_info "Checkpoint saved: $step"
}

# Define step order for resume logic
declare -A STEP_ORDER=(
    ["system_packages"]=1
    ["clone_repo"]=2
    ["firmware"]=3
    ["kernel_config"]=4
    ["hosts_file"]=5
    ["ssh_setup"]=6
    ["certificates"]=7
    ["deploy_stack"]=8
)

check_step() {
    local step=$1
    # If not resuming, always run the step
    if [[ "$RESUME" != true ]] || [[ -z "${LAST_COMPLETED_STEP:-}" ]]; then
        return 1  # Step not completed, should run
    fi

    # Get order of current step and last completed step
    local current_order=${STEP_ORDER[$step]:-999}
    local last_order=${STEP_ORDER[$LAST_COMPLETED_STEP]:-0}

    # If current step order is <= last completed step order, it was already completed
    if [[ $current_order -le $last_order ]]; then
        return 0  # Step completed, should skip
    else
        return 1  # Step not completed, should run
    fi
}

skip_if_completed() {
    local step=$1
    if check_step "$step"; then
        log_info "Step '$step' already completed. Skipping..."
        return 0
    fi
    return 1
}

# Main deployment steps
main() {
    if [[ "$ACTION" == "uninstall" ]]; then
        log_info "=========================================="
        log_info "Enterprise Inference Stack Uninstall"
        log_info "=========================================="
        log_info "Username: $USERNAME"
        log_info "Branch: $BRANCH"
        log_info "State File: $STATE_FILE"
        log_info "=========================================="
        echo ""

        if [[ -f "$STATE_FILE" ]]; then
            rm -f "$STATE_FILE"
            log_info "State file removed"
        fi

        if [[ ! -f "/home/${USERNAME}/Enterprise-Inference/core/inference-stack-deploy.sh" ]]; then
            log_error "inference-stack-deploy.sh not found at /home/${USERNAME}/Enterprise-Inference/core"
            exit 1
        fi

        log_info "Running inference-stack-deploy.sh decommission..."
        UNINSTALL_OUTPUT=$(su "${USERNAME}" -c "cd /home/${USERNAME}/Enterprise-Inference/core && echo -e '2\nyes\nlatest\nyes' | bash ./inference-stack-deploy.sh" 2>&1) || {
            log_error "Enterprise Inference Stack uninstall failed!"
            echo "$UNINSTALL_OUTPUT"
            exit 1
        }

        if echo "$UNINSTALL_OUTPUT" | grep -q "Reset operation cancelled"; then
            log_error "Uninstall was cancelled by the prompt."
            echo "$UNINSTALL_OUTPUT"
            exit 1
        fi

        if [[ -d "/home/${USERNAME}/Enterprise-Inference" ]]; then
            if [[ -f "/home/${USERNAME}/Enterprise-Inference/core/inference-stack-deploy.sh" ]]; then
                rm -f "/home/${USERNAME}/Enterprise-Inference/core/inference-stack-deploy.sh"
                log_info "Removed inference-stack-deploy.sh"
            fi
            log_info "Removing /home/${USERNAME}/Enterprise-Inference..."
            rm -rf "/home/${USERNAME}/Enterprise-Inference"
            log_success "Enterprise-Inference directory removed"
        fi

        log_success "Uninstall completed successfully!"
        exit 0
    fi

    log_info "=========================================="
    log_info "Enterprise Inference Stack Deployment"
    log_info "=========================================="
    log_info "Username: $USERNAME"
    log_info "GPU Type: $GPU_TYPE"
    log_info "Models: $MODELS"
    log_info "Branch: $BRANCH"
    log_info "Deployment Mode: $DEPLOYMENT_MODE"
    log_info "  - Keycloak + APISIX: $DEPLOY_KEYCLOAK_APISIX"
    log_info "  - GenAI Gateway: $DEPLOY_GENAI_GATEWAY"
    log_info "  - Observability: $DEPLOY_OBSERVABILITY"
    log_info "State File: $STATE_FILE"
    log_info "Resume Mode: $RESUME"
    log_info "=========================================="
    echo ""

    check_hf_token_access

    # Step 1: Install system packages
    if ! skip_if_completed "system_packages"; then
        log_info "Step 1: Installing system packages..."
        apt-get update
        apt-get install -y git openssl curl
        log_success "System packages installed"
        save_state "system_packages"
    fi

    # Step 2: Clone Enterprise Inference repository
    if ! skip_if_completed "clone_repo"; then
        log_info "Step 2: Cloning Enterprise Inference repository..."
        log_info "Repository: ${REPO_URL}"
        log_info "Branch: ${BRANCH}"
        if [[ -d "/home/${USERNAME}/Enterprise-Inference" ]]; then
            log_warn "Enterprise-Inference directory already exists. Skipping clone..."
        else
            cd "/home/${USERNAME}"
            su "${USERNAME}" -c "git clone --depth 1 --branch ${BRANCH} ${REPO_URL}"
            log_success "Repository cloned"
        fi

        # Create .become-passfile for Ansible (empty since we configure NOPASSWD)
        log_info "Creating Ansible become-passfile..."
        INVENTORY_DIR="/home/${USERNAME}/Enterprise-Inference/core/inventory"
        if [[ ! -d "$INVENTORY_DIR" ]]; then
            # Try alternative spelling (typo in some versions)
            INVENTORY_DIR="/home/${USERNAME}/Enterprise-Inference/core/inventory"
        fi

        if [[ -d "$INVENTORY_DIR" ]]; then
            BECOME_PASSFILE="${INVENTORY_DIR}/.become-passfile"
            # Create passfile with user password for Ansible
            echo "${USER_PASSWORD}" > "$BECOME_PASSFILE"
            chown "${USERNAME}:${USERNAME}" "$BECOME_PASSFILE"
            chmod 600 "$BECOME_PASSFILE"
            log_success "Ansible become-passfile created at ${BECOME_PASSFILE}"
        else
            log_warn "Inventory directory not found at ${INVENTORY_DIR}, will create later"
        fi
        if [[ "$GPU_TYPE" == "cpu" ]] || [[ "$GPU_TYPE" == "gaudi3" ]]; then
            CONFIG_FILE="/home/${USERNAME}/Enterprise-Inference/core/inventory/inference-config.cfg"
                if [[ -f "$CONFIG_FILE" ]]; then
                        sed -i -E \
                        -e 's/^[[:space:]]*hugging_face_token[[:space:]]*=.*/hugging_face_token='${HF_TOKEN}'/' \
                        -e 's/^[[:space:]]*models[[:space:]]*=.*/models='${MODELS}'/' \
                        -e 's/^[[:space:]]*cpu_or_gpu[[:space:]]*=.*/cpu_or_gpu='${GPU_TYPE}'/' \
                        -e 's/^[[:space:]]*keycloak_client_id[[:space:]]*=.*/keycloak_client_id='${KEYCLOAK_CLIENT_ID}'/' \
                        -e 's/^[[:space:]]*keycloak_admin_user[[:space:]]*=.*/keycloak_admin_user='${KEYCLOAK_ADMIN_USER}'/' \
                        -e 's/^[[:space:]]*keycloak_admin_password[[:space:]]*=.*/keycloak_admin_password='${KEYCLOAK_ADMIN_PASSWORD}'/' \
                        -e 's/^[[:space:]]*deploy_keycloak_apisix[[:space:]]*=.*/deploy_keycloak_apisix='${DEPLOY_KEYCLOAK_APISIX}'/' \
                        -e 's/^[[:space:]]*deploy_genai_gateway[[:space:]]*=.*/deploy_genai_gateway='${DEPLOY_GENAI_GATEWAY}'/' \
                        -e 's/^[[:space:]]*deploy_observability[[:space:]]*=.*/deploy_observability='${DEPLOY_OBSERVABILITY}'/' \
                        "$CONFIG_FILE"
                        log_info "Updated inference-config.cfg with models='${MODELS}' and cpu_or_gpu=${GPU_TYPE}"
                else
                log_warn "inference-config.cfg not found at $CONFIG_FILE, skipping update."
            fi
        fi

        # ------------------------------------------------------------
        # Disable NRI explicitly for CPU-only deployments
        # ------------------------------------------------------------
        if [[ "$GPU_TYPE" == "cpu" ]]; then
            log_info "CPU-only mode detected — disabling NRI and CPU balloons"

            # Update if keys exist
            sed -i -E \
              -e 's/^[[:space:]]*enable_nri[[:space:]]*=.*/enable_nri=false/' \
              -e 's/^[[:space:]]*enable_cpu_balloons[[:space:]]*=.*/enable_cpu_balloons=false/' \
              "$CONFIG_FILE" || true

            # Append if keys do not exist
            grep -q '^enable_nri=' "$CONFIG_FILE" || echo 'enable_nri=false' >> "$CONFIG_FILE"
            grep -q '^enable_cpu_balloons=' "$CONFIG_FILE" || echo 'enable_cpu_balloons=false' >> "$CONFIG_FILE"

            log_success "NRI disabled for CPU-only deployment"
        fi
        save_state "clone_repo"
    fi

    # Step 3: Install Gaudi3 firmware (only for gaudi3)
    if [[ "$GPU_TYPE" == "gaudi3" ]]; then
        if ! skip_if_completed "firmware"; then
            log_info "Step 3: Installing Gaudi3 firmware..."
            cd "/home/${USERNAME}/Enterprise-Inference/core"
            if [[ -f "scripts/firmware-update.sh" ]]; then
                chmod u+x scripts/firmware-update.sh
                scripts/firmware-update.sh "${FIRMWARE_VERSION}" --force || {
                    log_warn "Firmware update may have failed, continuing..."
                }
                log_success "Firmware installation completed"
            else
                log_warn "Firmware update script not found, skipping..."
            fi
            save_state "firmware"
        fi
    else
        log_info "Step 3: Skipping firmware (CPU mode)"
        save_state "firmware"
    fi

    # Step 4: Kernel configuration for kernel 6.8 (only for gaudi3)
    if [[ "$GPU_TYPE" == "gaudi3" ]]; then
        if ! skip_if_completed "kernel_config"; then
            log_info "Step 4: Checking kernel version and configuring IOMMU if needed..."
            KERNEL=$(uname -r)
            if [[ "$KERNEL" == 6.8.* ]]; then
                log_info "Kernel version 6.8 detected. Adding IOMMU configuration..."
                if ! grep -q "iommu=pt intel_iommu=on" /etc/default/grub; then
                    echo "" >> /etc/default/grub
                    echo "# Gaudi3 requires this option for kernel version 6.8" >> /etc/default/grub
                    echo 'GRUB_CMDLINE_LINUX_DEFAULT="iommu=pt intel_iommu=on"' >> /etc/default/grub
                    log_warn "IOMMU configuration added. System restart required after deployment."
                else
                    log_info "IOMMU configuration already present"
                fi
            else
                log_info "Kernel version $KERNEL - no special configuration needed"
            fi
            save_state "kernel_config"
        fi
    else
        log_info "Step 4: Skipping kernel config (CPU mode)"
        save_state "kernel_config"
    fi

    # Step 5: Add hostname to /etc/hosts
    if ! skip_if_completed "hosts_file"; then
        log_info "Step 5: Adding hostname to /etc/hosts..."
        if ! grep -q "api.example.com" /etc/hosts; then
            echo "" >> /etc/hosts
            echo "127.0.0.1 api.example.com" >> /etc/hosts
            log_success "Hostname added to /etc/hosts"
        else
            log_info "Hostname already in /etc/hosts"
        fi
        save_state "hosts_file"
    fi

    # Step 6: Setup SSH keys
    if ! skip_if_completed "ssh_setup"; then
        log_info "Step 6: Setting up SSH keys..."
        cd "/home/${USERNAME}"

        # Create .ssh directory if it doesn't exist
        su "${USERNAME}" -c "mkdir -p .ssh"

        # Generate SSH key if it doesn't exist
        if [[ ! -f "/home/${USERNAME}/.ssh/id_rsa" ]]; then
            su "${USERNAME}" -c "ssh-keygen -t rsa -b 4096 -f /home/${USERNAME}/.ssh/id_rsa -N '' -q"
            log_info "SSH key generated"
        else
            log_info "SSH key already exists"
        fi

        # Add public key to authorized_keys
        if [[ -f "/home/${USERNAME}/.ssh/id_rsa.pub" ]]; then
            PUB_KEY=$(cat "/home/${USERNAME}/.ssh/id_rsa.pub")
            if ! grep -q "$PUB_KEY" "/home/${USERNAME}/.ssh/authorized_keys" 2>/dev/null; then
                cat "/home/${USERNAME}/.ssh/id_rsa.pub" >> "/home/${USERNAME}/.ssh/authorized_keys"
                log_info "Public key added to authorized_keys"
            fi
        fi

        # Add to known_hosts
        su "${USERNAME}" -c "ssh-keyscan -H localhost >> /home/${USERNAME}/.ssh/known_hosts 2>/dev/null || true"
        su "${USERNAME}" -c "ssh-keyscan -H 127.0.0.1 >> /home/${USERNAME}/.ssh/known_hosts 2>/dev/null || true"

        # Set proper permissions
        chown -R "${USERNAME}:${USERNAME}" "/home/${USERNAME}/.ssh"
        chmod 700 "/home/${USERNAME}/.ssh"
        chmod 600 "/home/${USERNAME}/.ssh/id_rsa" 2>/dev/null || true
        chmod 644 "/home/${USERNAME}/.ssh/id_rsa.pub" 2>/dev/null || true
        chmod 600 "/home/${USERNAME}/.ssh/authorized_keys" 2>/dev/null || true

        log_success "SSH setup completed"
        save_state "ssh_setup"
    fi

    # Step 7: Create SSL certificates
    if ! skip_if_completed "certificates"; then
        log_info "Step 7: Creating SSL certificates..."
        cd "/home/${USERNAME}"
        su "${USERNAME}" -c "mkdir -p certs"
        cd certs

        if [[ ! -f "cert.pem" ]] || [[ ! -f "key.pem" ]]; then
            su "${USERNAME}" -c "openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=${CLUSTER_URL}'"
            log_success "SSL certificates created"
        else
            log_info "SSL certificates already exist"
        fi
        save_state "certificates"
    fi

    # Step 8: Deploy Enterprise Inference Stack
    if ! skip_if_completed "deploy_stack"; then
        log_info "Step 8: Deploying Enterprise Inference Stack..."
        cd "/home/${USERNAME}/Enterprise-Inference/core"

        if [[ ! -f "inference-stack-deploy.sh" ]]; then
            log_error "inference-stack-deploy.sh not found!"
            exit 1
        fi

        chmod +x inference-stack-deploy.sh

        # Configure sudo NOPASSWD for the user (required for Ansible)
        log_info "Configuring sudo NOPASSWD for user ${USERNAME}..."
        if ! grep -q "^${USERNAME}.*NOPASSWD" /etc/sudoers 2>/dev/null; then
            echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
            log_success "Sudo NOPASSWD configured for ${USERNAME}"
        else
            log_info "Sudo NOPASSWD already configured for ${USERNAME}"
        fi


        log_info "Applying single-node inventory defaults..."
        SRC_BASE="/home/${USERNAME}/Enterprise-Inference/docs/examples/single-node"
        DEST_BASE="/home/${USERNAME}/Enterprise-Inference/core/inventory"

        if [[ -d "$SRC_BASE" ]] && [[ -d "$DEST_BASE" ]]; then
            cp -f "${SRC_BASE}/hosts.yaml" "${DEST_BASE}/hosts.yaml"
            chown "${USERNAME}:${USERNAME}" "${DEST_BASE}/hosts.yaml"
            log_success "Single-node hosts.yaml applied"
        else
            log_warn "Single-node example for hosts not found, skipping copy"
        fi


        # Ensure .become-passfile exists (created in Step 2, but verify here)
        log_info "Verifying Ansible become-passfile..."
        INVENTORY_DIR="/home/${USERNAME}/Enterprise-Inference/core/inventory"
        if [[ ! -d "$INVENTORY_DIR" ]]; then
            # Try alternative spelling (typo in docs)
            INVENTORY_DIR="/home/${USERNAME}/Enterprise-Inference/core/inentory"
        fi

        if [[ -d "$INVENTORY_DIR" ]]; then
            BECOME_PASSFILE="${INVENTORY_DIR}/.become-passfile"
            if [[ ! -f "$BECOME_PASSFILE" ]]; then
                # Create passfile with user password for Ansible
                echo "${USER_PASSWORD}" > "$BECOME_PASSFILE"
                chown "${USERNAME}:${USERNAME}" "$BECOME_PASSFILE"
                chmod 600 "$BECOME_PASSFILE"
                log_info "Ansible become-passfile created"
            else
                # Update passfile with current password
                echo "${USER_PASSWORD}" > "$BECOME_PASSFILE"
                chown "${USERNAME}:${USERNAME}" "$BECOME_PASSFILE"
                chmod 600 "$BECOME_PASSFILE"
                log_info "Ansible become-passfile updated"
            fi
        else
            log_warn "Inventory directory not found at ${INVENTORY_DIR}"
        fi

        HOSTS_FILE="/home/${USERNAME}/Enterprise-Inference/core/inventory/hosts.yaml"

	    if [[ -f "$HOSTS_FILE" ]]; then
    	   log_info "Updating ansible_user in hosts.yaml to '${USERNAME}'"

           sed -i -E "/^[[:space:]]*master1:/,/^[[:space:]]{2}children:/ s/^([[:space:]]*ansible_user:[[:space:]]*).*/\1${USERNAME}/" "$HOSTS_FILE"
        else
            log_warn "hosts.yaml not found at ${HOSTS_FILE}, skipping ansible_user update"
        fi

        # Export Hugging Face token
        export HUGGINGFACE_TOKEN="${HF_TOKEN}"

        log_info "Running inference-stack-deploy.sh..."
        log_info "Parameters: --models '${MODELS}' --cpu-or-gpu '${GPU_TYPE}' --hugging-face-token <token>"

        # Run the deployment script
        if [[ "$FORCE_INTERACTIVE_DEPLOY" == true ]]; then
            log_info "State file indicates a prior deployment; running interactively"
            CONFIG_FILE="/home/${USERNAME}/Enterprise-Inference/core/inventory/inference-config.cfg"
            update_inference_config
            su "${USERNAME}" -c "cd /home/${USERNAME}/Enterprise-Inference/core && bash ./inference-stack-deploy.sh --cpu-or-gpu '${GPU_TYPE}' --hugging-face-token ${HUGGINGFACE_TOKEN}" || {
                log_error "Enterprise Inference Stack deployment failed!"
                log_warn "You can resume by running this script again with -r flag"
                exit 1
            }
        else
            # Using echo to provide input: "1" for "Provision Enterprise Inference Cluster", "yes" for confirmation
            su "${USERNAME}" -c "cd /home/${USERNAME}/Enterprise-Inference/core && echo -e '1\nyes' | bash ./inference-stack-deploy.sh --models '${MODELS}' --cpu-or-gpu '${GPU_TYPE}' --hugging-face-token ${HUGGINGFACE_TOKEN}" || {
                log_error "Enterprise Inference Stack deployment failed!"
                log_warn "You can resume by running this script again with -r flag"
                exit 1
            }
        fi

        log_success "Enterprise Inference Stack deployed successfully!"
        save_state "deploy_stack"
    fi

    # Cleanup state file on successful completion
    if [[ -f "$STATE_FILE" ]]; then
        rm -f "$STATE_FILE"
        log_info "State file cleaned up"
    fi

    log_success "=========================================="
    log_success "Deployment completed successfully!"
    log_success "=========================================="
    log_info "  - Mode: ${DEPLOYMENT_MODE}"
    log_info "  - GPU Type: ${GPU_TYPE}"
    log_info "  - Models: ${MODELS}"
	log_info "  - Observability: ${DEPLOY_OBSERVABILITY}"
}

# Run main function
main "$@"