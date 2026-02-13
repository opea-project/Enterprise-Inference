#!/bin/bash

# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

#=============================================================================
# vLLM Model Launcher
# A modular script to launch different LLM models with vLLM
#=============================================================================

# Configuration
readonly CONFIG_FILE="models.json"
readonly LOG_FILE="/tmp/vllm-startup.log"
readonly CONTAINER_NAME="vllm-container"

# Port configuration (can be overridden via command line)
PORT="8000"
HEALTHCHECK_URL="http://localhost:${PORT}/health"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly BLUE='\033[0;34m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'

#=============================================================================
# ARGUMENT PARSING
#=============================================================================

# Display usage information
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p, --port PORT    Port to run the vLLM server on (default: 8000)"
    echo "  -h, --help         Display this help message"
    echo ""
    echo "Examples:"
    echo "  $0                  # Start vLLM on default port 8000"
    echo "  $0 -p 8080          # Start vLLM on port 8080"
    echo "  $0 --port 9000      # Start vLLM on port 9000"
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -p|--port)
                if [[ -z "$2" || "$2" == -* ]]; then
                    echo "Error: --port requires a port number"
                    show_usage
                    exit 1
                fi
                # Validate port number
                if ! [[ "$2" =~ ^[0-9]+$ ]] || (( $2 < 1 || $2 > 65535 )); then
                    echo "Error: Invalid port number '$2'. Must be between 1 and 65535."
                    exit 1
                fi
                PORT="$2"
                shift 2
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                echo "Error: Unknown option '$1'"
                show_usage
                exit 1
                ;;
        esac
    done

    # Update HEALTHCHECK_URL with the configured port
    HEALTHCHECK_URL="http://localhost:${PORT}/health"
}

#=============================================================================
# UTILITY FUNCTIONS
#=============================================================================

# Logging function with levels and colors
log() {
    local level="$1"
    local message="$2"
    local color="$NC"

    case "$level" in
        INFO) color="$BLUE" ;;
        SUCCESS) color="$GREEN" ;;
        ERROR) color="$RED" ;;
        WARN) color="$YELLOW" ;;
    esac

    # Use echo instead of printf and redirect to ensure clean output
    echo -e "${color}[${level}]${NC} ${message}"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [$level] $message" >> "$LOG_FILE"
}

# Clean exit function
cleanup_and_exit() {
    local exit_code="${1:-1}"
    local message="${2:-Script terminated}"

    if [[ "$exit_code" -ne 0 ]]; then
        log "ERROR" "$message"
        printf "${RED}❌ %s${NC}\n" "$message"
        printf "${YELLOW}Check %s for detailed logs.${NC}\n" "$LOG_FILE"
    fi

    exit "$exit_code"
}

#=============================================================================
# CONFIGURATION FUNCTIONS
#=============================================================================

# Install Docker following official Ubuntu installation guide
install_docker() {
    log "INFO" "Installing Docker..."

    # Update package index
    sudo apt-get update -y >/dev/null 2>&1

    # Install prerequisite packages
    sudo apt-get install -y ca-certificates curl gnupg lsb-release >/dev/null 2>&1

    # Add Docker's official GPG key
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg >/dev/null 2>&1

    # Set up the Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

    # Update package index with Docker repository
    sudo apt-get update -y >/dev/null 2>&1

    # Install Docker Engine
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1

    # Add current user to docker group to run docker without sudo
    sudo usermod -aG docker $USER

    # Start and enable Docker service
    sudo systemctl start docker
    sudo systemctl enable docker

    log "SUCCESS" "Docker installed successfully"
    log "WARN" "Please log out and log back in for Docker group membership to take effect"
    log "WARN" "Or run: newgrp docker"
}

# Install jq JSON processor
install_jq() {
    log "INFO" "Installing jq..."
    sudo apt-get update -y >/dev/null 2>&1
    sudo apt-get install -y jq >/dev/null 2>&1
    log "SUCCESS" "jq installed successfully"
}

# Install curl if missing
install_curl() {
    log "INFO" "Installing curl..."
    sudo apt-get update -y >/dev/null 2>&1
    sudo apt-get install -y curl >/dev/null 2>&1
    log "SUCCESS" "curl installed successfully"
}

# Install git if missing
install_git() {
    log "INFO" "Installing git..."
    sudo apt-get update -y >/dev/null 2>&1
    sudo apt-get install -y git >/dev/null 2>&1
    log "SUCCESS" "git installed successfully"
}

# Clone vLLM repository to /opt/vllm
clone_vllm_repository() {
    local vllm_path="/opt/vllm"

    log "INFO" "Setting up vLLM repository at $vllm_path..."

    # Check if directory already exists and has content
    if [[ -d "$vllm_path" && -n "$(sudo ls -A "$vllm_path" 2>/dev/null)" ]]; then
        log "INFO" "vLLM repository already exists at $vllm_path"

        # Check if it's a git repository and has the examples directory
        if sudo test -d "$vllm_path/.git" && sudo test -d "$vllm_path/examples"; then
            log "INFO" "Updating existing vLLM repository..."
            if sudo git -C "$vllm_path" pull origin main >> "$LOG_FILE" 2>&1; then
                log "SUCCESS" "vLLM repository updated successfully"
                return 0
            else
                log "WARN" "Failed to update vLLM repository, re-cloning..."
                sudo rm -rf "$vllm_path"
                clone_vllm_repo_fresh "$vllm_path"
            fi
        else
            log "WARN" "Directory exists but is not a proper vLLM repository, removing and re-cloning..."
            sudo rm -rf "$vllm_path"
            clone_vllm_repo_fresh "$vllm_path"
        fi
    else
        clone_vllm_repo_fresh "$vllm_path"
    fi

    # Final verification that examples directory exists
    if ! sudo test -d "$vllm_path/examples"; then
        log "ERROR" "vLLM examples directory not found after cloning"
        return 1
    fi

    log "SUCCESS" "vLLM repository setup completed"
    return 0
}

# Helper function to clone fresh repository
clone_vllm_repo_fresh() {
    local vllm_path="$1"

    log "INFO" "Cloning vLLM repository from GitHub..."

    # Create parent directory if it doesn't exist
    sudo mkdir -p "$(dirname "$vllm_path")" 2>/dev/null || true

    # Clone the repository
    if sudo git clone --depth 1 https://github.com/vllm-project/vllm.git "$vllm_path" >> "$LOG_FILE" 2>&1; then
        log "SUCCESS" "vLLM repository cloned successfully"

        # Set proper permissions for better access (optional, but helpful for debugging)
        sudo chown -R root:root "$vllm_path"
        sudo chmod -R 755 "$vllm_path"
    else
        log "ERROR" "Failed to clone vLLM repository"
        return 1
    fi
}

# Check and install required dependencies
install_dependencies() {
    log "INFO" "Checking and installing prerequisites..."

    local need_newgrp=false
    local need_rerun=false

    # Check if we have sudo privileges
    if ! sudo -n true 2>/dev/null; then
        log "WARN" "This script requires sudo privileges to install dependencies"
        log "INFO" "Please run: sudo -v"
        read -p "Press Enter after running sudo -v to continue..."
    fi

    # Check and install curl first (needed for Docker installation)
    if ! command -v curl >/dev/null 2>&1; then
        install_curl
    fi

    # Check and install git (needed for vLLM repository cloning)
    if ! command -v git >/dev/null 2>&1; then
        install_git
    fi

    # Check and install jq
    if ! command -v jq >/dev/null 2>&1; then
        install_jq
    fi

    # Check and install Docker
    if ! command -v docker >/dev/null 2>&1; then
        install_docker
        need_newgrp=true
        need_rerun=true
    fi

    # Setup vLLM repository (needed for examples volume mount)
    if ! clone_vllm_repository; then
        cleanup_and_exit 1 "Failed to setup vLLM repository"
    fi    # Check if current user is in docker group

    if ! groups | grep -q docker; then
        log "WARN" "Current user is not in docker group"
        # Check if we can still access Docker with sudo
        if sudo docker info >/dev/null 2>&1; then
            log "INFO" "Docker accessible with sudo, continuing..."
        else
            if [[ "$need_newgrp" == "false" ]]; then
                log "INFO" "Adding user to docker group..."
                sudo usermod -aG docker $USER
                need_rerun=true
            fi
        fi
    fi

    # If user was added to docker group, suggest re-running
    if [[ "$need_rerun" == "true" ]]; then
        log "WARN" "User has been added to docker group"
        log "WARN" "Please run: newgrp docker"
        log "WARN" "Then re-run this script, or log out and log back in"
        exit 1
    fi

    log "SUCCESS" "All prerequisites are satisfied"
}

# Validate required dependencies
validate_dependencies() {
    # First try to install missing dependencies
    install_dependencies

    # Then validate that everything is working
    local missing_deps=()

    command -v jq >/dev/null || missing_deps+=("jq")
    command -v docker >/dev/null || missing_deps+=("docker")
    command -v curl >/dev/null || missing_deps+=("curl")

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        cleanup_and_exit 1 "Failed to install dependencies: ${missing_deps[*]}. Please install them manually."
    fi
}

# Validate environment and prerequisites
validate_environment() {
    log "INFO" "Validating environment..."

    # Check HuggingFace token
    if [[ -z "$HFToken" ]]; then
        cleanup_and_exit 1 "HUGGING_FACE_HUB_TOKEN (HFToken) is not set. Please export HFToken before running."
    fi

    # Check config file
    if [[ ! -f "$CONFIG_FILE" ]]; then
        cleanup_and_exit 1 "Configuration file $CONFIG_FILE not found."
    fi

    # Validate JSON syntax
    if ! jq empty "$CONFIG_FILE" 2>/dev/null; then
        cleanup_and_exit 1 "Invalid JSON syntax in $CONFIG_FILE"
    fi

    # Check Docker daemon
    check_docker_access
    if ! ${USE_SUDO}docker info >/dev/null 2>&1; then
        cleanup_and_exit 1 "Docker daemon is not running or not accessible."
    fi

    log "SUCCESS" "Environment validation completed"
}

# Global variables for model data
declare -a MODEL_KEYS
declare -g USE_SUDO=""

# Helper function to determine if we need sudo for Docker
check_docker_access() {
    if groups | grep -q docker; then
        USE_SUDO=""
    else
        USE_SUDO="sudo "
        log "WARN" "User not in docker group, using sudo for Docker commands"
    fi
}

# Load and parse configuration
load_configuration() {
    log "INFO" "Loading configuration from $CONFIG_FILE"

    # Extract model list
    local temp_keys
    if ! temp_keys=($(jq -r '.models | keys[]' "$CONFIG_FILE" 2>/dev/null)); then
        cleanup_and_exit 1 "Failed to parse model keys from configuration"
    fi

    if [[ ${#temp_keys[@]} -eq 0 ]]; then
        cleanup_and_exit 1 "No models found in configuration"
    fi

    # Assign to global array
    MODEL_KEYS=("${temp_keys[@]}")

    log "SUCCESS" "Loaded ${#MODEL_KEYS[@]} model configurations"
}

#=============================================================================
# HARDWARE DETECTION FUNCTIONS
#=============================================================================

# Compute parallel configuration based on hardware
compute_parallel_config() {
    log "INFO" "Detecting hardware configuration..." >&2

    local total_sockets total_numa_nodes numa_per_socket

    total_sockets=$(lscpu | grep 'Socket(s):' | awk '{print $2}' 2>/dev/null)
    total_numa_nodes=$(lscpu | grep 'NUMA node(s):' | awk '{print $3}' 2>/dev/null)

    # Validate hardware detection
    if [[ -z "$total_sockets" || -z "$total_numa_nodes" ]]; then
        log "WARN" "Could not detect hardware configuration. Using default settings." >&2
        echo ""
        return
    fi

    if [[ "$total_sockets" -eq 0 ]]; then
        log "WARN" "Invalid socket count detected. Using default settings." >&2
        echo ""
        return
    fi

    numa_per_socket=$((total_numa_nodes / total_sockets))

    local parallel_config=""
    case "$numa_per_socket" in
        2|4)
            parallel_config="--tensor-parallel-size $numa_per_socket"
            log "INFO" "Using tensor parallelism: $numa_per_socket" >&2
            ;;
        3|6)
            parallel_config="--pipeline-parallel-size $numa_per_socket"
            log "INFO" "Using pipeline parallelism: $numa_per_socket" >&2
            ;;
        *)
            log "INFO" "No specific parallelism configuration for $numa_per_socket NUMA nodes per socket" >&2
            ;;
    esac

    echo "$parallel_config"
}

#=============================================================================
# USER INTERACTION FUNCTIONS
#=============================================================================

# Display available models and get user selection
select_model() {
    printf "${YELLOW}Available Models:${NC}\n" >&2
    echo >&2

    for i in "${!MODEL_KEYS[@]}"; do
        local model_key="${MODEL_KEYS[$i]}"
        local display_name
        display_name=$(jq -r ".models.\"$model_key\".display_name" "$CONFIG_FILE")
        printf "%2d) %s\n" "$((i+1))" "$display_name" >&2
    done

    echo >&2
    printf "${YELLOW}Enter the number of the model you want to start:${NC}\n" >&2
    read -p "> " choice

    # Validate user input
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || (( choice < 1 || choice > ${#MODEL_KEYS[@]} )); then
        cleanup_and_exit 1 "Invalid choice: $choice. Please enter a number between 1 and ${#MODEL_KEYS[@]}."
    fi

    # Return selected model key
    echo "${MODEL_KEYS[$((choice-1))]}"
}

#=============================================================================
# DOCKER MANAGEMENT FUNCTIONS
#=============================================================================

# Build vLLM arguments from configuration
build_vllm_args() {
    local model_key="$1"
    local parallel_config="$2"

    log "INFO" "Building vLLM arguments for model: $model_key" >&2

    # Get model path
    local model_path
    model_path=$(jq -r ".models.\"$model_key\".model_path" "$CONFIG_FILE")

    if [[ "$model_path" == "null" || -z "$model_path" ]]; then
        cleanup_and_exit 1 "Model path not found for $model_key"
    fi

    # Start building arguments
    local args="--model $model_path"

    # Add global defaults
    while IFS='=' read -r key value; do
        if [[ "$value" == "true" ]]; then
            args="$args --$key"
        elif [[ "$value" != "false" && "$value" != "null" ]]; then
            args="$args --$(echo "$key" | tr '_' '-') $value"
        fi
    done < <(jq -r '.global_defaults | to_entries[] | "\(.key)=\(.value)"' "$CONFIG_FILE")

    # Add model-specific arguments
    while IFS='=' read -r key value; do
        if [[ "$value" == "true" ]]; then
            args="$args --$key"
        elif [[ "$value" != "false" && "$value" != "null" ]]; then
            args="$args --$(echo "$key" | tr '_' '-') $value"
        fi
    done < <(jq -r ".models.\"$model_key\".vllm_args | to_entries[] | \"\(.key)=\(.value)\"" "$CONFIG_FILE" 2>/dev/null)

    # Add parallel configuration
    if [[ -n "$parallel_config" ]]; then
        args="$args $parallel_config"
    fi

    echo "$args"
}

# Stop existing vLLM container
stop_existing_container() {
    log "INFO" "Checking for existing vLLM containers..."

    # Check for both running and stopped containers with the same name
    local existing_container
    existing_container=$(${USE_SUDO}docker ps -aq --filter "name=$CONTAINER_NAME" 2>/dev/null)

    if [[ -n "$existing_container" ]]; then
        log "INFO" "Stopping existing container: $existing_container"

        # Stop the container if it's running
        if ${USE_SUDO}docker ps -q --filter "name=$CONTAINER_NAME" | grep -q "$existing_container"; then
            if ! ${USE_SUDO}docker stop "$existing_container" >> "$LOG_FILE" 2>&1; then
                log "WARN" "Failed to stop container gracefully, forcing removal"
                ${USE_SUDO}docker kill "$existing_container" >> "$LOG_FILE" 2>&1
            fi
        fi

        # Try to remove the container - it might already be gone if started with --rm
        if ${USE_SUDO}docker inspect "$existing_container" >/dev/null 2>&1; then
            # Container still exists, try to remove it
            local retry_count=0
            local max_retries=5
            while [[ $retry_count -lt $max_retries ]]; do
                local rm_output
                rm_output=$(${USE_SUDO}docker rm "$existing_container" 2>&1)
                local rm_exit_code=$?

                if [[ $rm_exit_code -eq 0 ]]; then
                    log "SUCCESS" "Existing container stopped and removed"
                    return 0
                elif [[ "$rm_output" == *"No such container"* ]]; then
                    # Container was removed while we were trying (probably auto-removed with --rm)
                    log "SUCCESS" "Container was removed automatically"
                    return 0
                elif [[ "$rm_output" == *"removal of container"*"is already in progress"* ]]; then
                    # Docker is already removing it, wait a bit longer
                    log "INFO" "Container removal in progress, waiting..."
                    sleep 3
                else
                    # Some other error, log it
                    echo "$rm_output" >> "$LOG_FILE"
                    log "WARN" "Attempt $((retry_count + 1))/$max_retries: Failed to remove container, retrying in 2 seconds..."
                    sleep 2
                fi

                retry_count=$((retry_count + 1))
            done

            log "ERROR" "Failed to remove existing container after $max_retries attempts"
            return 1
        else
            # Container was already removed (probably had --rm flag)
            log "SUCCESS" "Existing container was already removed automatically"
            return 0
        fi
    else
        log "INFO" "No existing containers found"
    fi
}

# Check if Docker image exists locally
check_docker_image_exists() {
    local docker_image="$1"
    ${USE_SUDO}docker image inspect "$docker_image" >/dev/null 2>&1
}

# Pull Docker image if needed
pull_docker_image() {
    local docker_image="$1"

    log "INFO" "Checking if Docker image '$docker_image' exists locally..."

    if check_docker_image_exists "$docker_image"; then
        log "INFO" "Docker image already exists locally, checking for updates..."
    else
        log "INFO" "Docker image not found locally, downloading..."
    fi

    log "INFO" "Pulling Docker image (this may take several minutes on first run)..."

    # Show progress while pulling
    if ! ${USE_SUDO}docker pull "$docker_image" >> "$LOG_FILE" 2>&1; then
        log "ERROR" "Failed to pull Docker image: $docker_image"
        return 1
    fi

    log "SUCCESS" "Docker image pull completed"
    return 0
}

# Wait for container to be in running state
wait_for_container_running() {
    local max_attempts=60  # Wait up to 60 seconds for container to start
    local attempt=1

    log "INFO" "Waiting for container to enter running state..."

    while [[ $attempt -le $max_attempts ]]; do
        # Check if container exists and get its status
        local container_status
        container_status=$(${USE_SUDO}docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null)

        case "$container_status" in
            "running")
                log "SUCCESS" "Container is now running"
                return 0
                ;;
            "created"|"restarting")
                log "INFO" "Container is starting (attempt $attempt/$max_attempts)..."
                ;;
            "exited"|"dead")
                log "ERROR" "Container exited unexpectedly. Check container logs:"
                ${USE_SUDO}docker logs --tail=20 "$CONTAINER_NAME" >> "$LOG_FILE" 2>&1
                return 1
                ;;
            "")
                log "INFO" "Container not found yet (attempt $attempt/$max_attempts)..."
                ;;
            *)
                log "WARN" "Container in unexpected state: $container_status (attempt $attempt/$max_attempts)"
                ;;
        esac

        sleep 1
        ((attempt++))
    done

    log "ERROR" "Container did not reach running state within $max_attempts seconds"
    return 1
}

# Build and execute Docker command
start_vllm_container() {
    local model_key="$1"
    local vllm_args="$2"

    log "INFO" "Starting vLLM container for model: $model_key"

    # Get Docker image first
    local docker_image
    docker_image=$(jq -r '.docker.image' "$CONFIG_FILE")

    # Pull the image first to avoid confusion during container start
    if ! pull_docker_image "$docker_image"; then
        return 1
    fi

    # Build Docker command
    local docker_cmd="${USE_SUDO}docker run -d --name $CONTAINER_NAME"

    # Add port mapping (use user-specified PORT, mapping host port to container port 8000)
    docker_cmd="$docker_cmd -p ${PORT}:8000"

    # Add environment variables
    docker_cmd="$docker_cmd -e HUGGING_FACE_HUB_TOKEN=$HFToken"
    while IFS='=' read -r key value; do
        docker_cmd="$docker_cmd -e $key=$value"
    done < <(jq -r '.docker.environment | to_entries[] | "\(.key)=\(.value)"' "$CONFIG_FILE")

    # Add volume mounts
    while read -r volume; do
        [[ -n "$volume" ]] && docker_cmd="$docker_cmd -v $volume"
    done < <(jq -r '.docker.volumes[]?' "$CONFIG_FILE")

    # Add Docker image and vLLM arguments
    docker_cmd="$docker_cmd --ipc=host $docker_image $vllm_args"

    # Log the command for debugging (truncate if too long to avoid console wrapping)
    if [[ ${#docker_cmd} -gt 80 ]]; then
        log "INFO" "Docker command: ${docker_cmd:0:80}..."
        echo "Full Docker command: $docker_cmd" >> "$LOG_FILE"
    else
        log "INFO" "Docker command: $docker_cmd"
    fi

    log "INFO" "Starting container in detached mode..."

    # Execute Docker command and capture the container ID
    local container_id
    if ! container_id=$(eval "$docker_cmd" 2>> "$LOG_FILE"); then
        log "ERROR" "Failed to start Docker container. Check the log file for details."
        log "ERROR" "Recent log entries:"
        tail -10 "$LOG_FILE" | while read -r line; do
            log "ERROR" "  $line"
        done
        return 1
    fi

    log "INFO" "Container created with ID: ${container_id:0:12}..."

    # Wait for container to be in running state
    if ! wait_for_container_running; then
        log "ERROR" "Container failed to reach running state"
        return 1
    fi

    return 0
}

#=============================================================================
# HEALTH CHECK FUNCTIONS
#=============================================================================

# Perform health check on the started service
perform_health_check() {
    log "INFO" "Starting health check on $HEALTHCHECK_URL"
    log "INFO" "The vLLM server may take a few minutes to initialize and load the model..."
    sleep 10   # Allow vLLM container to begin initialization before polling

    local max_attempts=120  # Number of health check attempts to allow for model loading
    local attempt=1
    local last_container_status=""

    while [[ $attempt -le $max_attempts ]]; do
        # Check container status first
        local container_status
        container_status=$(${USE_SUDO}docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null)

        if [[ "$container_status" != "$last_container_status" ]]; then
            case "$container_status" in
                "running")
                    log "INFO" "Container is running, waiting for vLLM server to initialize..."
                    ;;
                "exited"|"dead")
                    log "ERROR" "Container has stopped unexpectedly. Checking logs..."
                    ${USE_SUDO}docker logs --tail=20 "$CONTAINER_NAME" >> "$LOG_FILE" 2>&1
                    return 1
                    ;;
                "")
                    log "ERROR" "Container not found during health check"
                    return 1
                    ;;
            esac
            last_container_status="$container_status"
        fi

        # Only proceed with health check if container is running
        if [[ "$container_status" == "running" ]]; then
            # Show periodic progress
            if (( attempt % 5 == 1 )); then
                log "INFO" "Health check attempt $attempt/$max_attempts - waiting for vLLM server response..."
            fi

            # Perform the actual health check
            local http_code
            http_code=$(curl -s --max-time 5 -w "%{http_code}" -o /dev/null "$HEALTHCHECK_URL" 2>/dev/null)

            if [[ "$http_code" == "200" ]]; then
                log "SUCCESS" "vLLM server is healthy and responding"
                printf "${GREEN}✅ vLLM server is running successfully at %s${NC}\n" "$HEALTHCHECK_URL"
                return 0
            elif [[ -n "$http_code" && "$http_code" != "000" ]]; then
                # We got a response but not 200, show what we got
                if (( attempt % 10 == 1 )); then
                    log "INFO" "Server responding with HTTP $http_code, still initializing..."
                fi
            fi
        fi

        sleep 5
        ((attempt++))
    done

    log "ERROR" "Health check failed after $max_attempts attempts"
    printf "${RED}❌ vLLM server failed to start or is not responding${NC}\n"
    printf "${YELLOW}The server may still be initializing. Check logs with: ${USE_SUDO}docker logs %s${NC}\n" "$CONTAINER_NAME"
    return 1
}

#=============================================================================
# MAIN FUNCTION
#=============================================================================

main() {
    # Parse command line arguments first
    parse_arguments "$@"

    # Initialize logging
    : > "$LOG_FILE"
    log "INFO" "Starting vLLM Model Launcher"
    log "INFO" "Server will run on port: $PORT"

    # Validate environment
    validate_dependencies
    validate_environment

    # Load configuration
    load_configuration

    # Hardware detection
    local parallel_config
    parallel_config=$(compute_parallel_config)

    # User interaction
    local selected_model
    selected_model=$(select_model)
    log "INFO" "User selected model: $selected_model"

    # Build configuration
    local vllm_args
    vllm_args=$(build_vllm_args "$selected_model" "$parallel_config")

    # Container management
    if ! stop_existing_container; then
        cleanup_and_exit 1 "Failed to remove existing containers"
    fi

    if ! start_vllm_container "$selected_model" "$vllm_args"; then
        cleanup_and_exit 1 "Failed to start vLLM container"
    fi

    # Health check
    if perform_health_check; then
        log "SUCCESS" "vLLM deployment completed successfully"
        exit 0
    else
        cleanup_and_exit 1 "vLLM deployment failed"
    fi
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
