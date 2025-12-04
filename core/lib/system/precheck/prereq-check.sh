# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

run_system_prerequisites_check() {
    echo "Running system prerequisites check..."
    echo "This will verify minimum system dependencies required for deployment."

    local missing_deps=()
    local warnings=()        
    echo "Checking essential system commands..."
    
    # Wait for dpkg lock to be released if present
    dpkg_lock_file="/var/lib/dpkg/lock"
    dpkg_lock_frontend="/var/lib/dpkg/lock-frontend"
    dpkg_lock_files=("$dpkg_lock_file" "$dpkg_lock_frontend")
    timeout=300
    for lock in "${dpkg_lock_files[@]}"; do
        waited=0
        if command -v lsof &>/dev/null; then
            while lsof "$lock" &>/dev/null && [ $waited -lt $timeout ]; do
                echo -e "${YELLOW}dpkg/apt process is using $lock (checked via lsof). Waiting for it to finish...${NC}"
                sleep 2
                waited=$((waited + 2))
            done
        elif command -v fuser &>/dev/null; then
            while fuser "$lock" &>/dev/null && [ $waited -lt $timeout ]; do
                echo -e "${YELLOW}dpkg/apt process is using $lock (checked via fuser). Waiting for it to finish...${NC}"
                sleep 2
                waited=$((waited + 2))
            done
        fi
        if [ $waited -ge $timeout ]; then
            if (command -v lsof &>/dev/null && lsof "$lock" &>/dev/null) || \
            (command -v fuser &>/dev/null && fuser "$lock" &>/dev/null); then
                echo -e "${RED}Timeout waiting for dpkg/apt lock file $lock to be released. Proceeding anyway.${NC}"
            fi
        fi
    done

    # Check for git
    if ! command -v git &> /dev/null; then
        missing_deps+=("git")
    else
        echo -e "${GREEN}✓ git found${NC}"
    fi
    
    


    # Check for python3 (version 3.10 or above) using configured interpreter
    if [ -z "$python3_interpreter" ]; then
        echo -e "${RED}✗ python3_interpreter not configured${NC}"
        missing_deps+=("python3 (interpreter not configured)")
    elif ! command -v "$python3_interpreter" &> /dev/null; then
        echo -e "${RED}✗ configured python interpreter not found: $python3_interpreter${NC}"
        missing_deps+=("python3")
    else
        # Check Python version using the configured interpreter
        python_version=$($python3_interpreter -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if $python3_interpreter -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            echo -e "${GREEN}✓ python3 found (version $python_version) at $python3_interpreter${NC}"
        else
            echo -e "${RED}✗ python3 version $python_version found at $python3_interpreter, but version 3.10+ required${NC}"
            missing_deps+=("python3 (version 3.10+)")
        fi
    fi
    
    # Check for curl (needed for pip installation)
    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    else
        echo -e "${GREEN}✓ curl found${NC}"
    fi
    
    # Check internet connectivity (essential for Docker images, packages, repositories)
    echo "Checking internet connectivity..."
    if command -v curl &> /dev/null; then
        # Test multiple reliable endpoints to ensure connectivity
        if curl -s --connect-timeout 10 --max-time 15 https://google.com > /dev/null 2>&1 || \
           curl -s --connect-timeout 10 --max-time 15 https://github.com > /dev/null 2>&1 || \
           curl -s --connect-timeout 10 --max-time 15 https://registry-1.docker.io > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Internet connectivity confirmed${NC}"
        else
            echo -e "${RED}✗ No internet connectivity detected${NC}"
            missing_deps+=("internet-connectivity")
        fi
    else
        # If curl is not available, we'll check this later after curl is installed
        warnings+=("Internet connectivity check skipped - curl not available")
    fi
    
    # Check if pip is available for the configured Python interpreter
    if [ -n "$python3_interpreter" ]; then
        if ! $python3_interpreter -m pip --version &> /dev/null; then
            missing_deps+=("pip")
        else
            pip_version=$($python3_interpreter -m pip --version 2>/dev/null | cut -d' ' -f2)
            echo -e "${GREEN}✓ pip found for $python3_interpreter (version $pip_version)${NC}"
        fi
    else
        warnings+=("python3_interpreter not configured - pip check skipped")
    fi
    
    # Check for virtualenv capability (can be installed via pip)
    if [ -n "$python3_interpreter" ] && ! $python3_interpreter -c "import venv" &> /dev/null && ! $python3_interpreter -c "import virtualenv" &> /dev/null; then
        warnings+=("virtualenv not available - will be installed during setup")
    else
        echo -e "${GREEN}✓ virtualenv capability found${NC}"
    fi
    
    # Display warnings
    if [ ${#warnings[@]} -gt 0 ]; then
        echo -e "${YELLOW}Warnings:${NC}"
        for warning in "${warnings[@]}"; do
            echo -e "${YELLOW}  ! $warning${NC}"
        done
    fi
    

    echo "Updating system package lists..."
    if command -v apt &> /dev/null; then
        echo "Updating package lists using apt Ubuntu..."
        if sudo -S apt update < "${BECOME_PASSWORD_FILE}"; then
            echo -e "${GREEN}Package lists updated successfully${NC}"
        else
            echo -e "${YELLOW}Package list update failed, continuing anyway${NC}"
        fi
    elif command -v dnf &> /dev/null; then
        echo "Updating package lists using dnf (RHEL/CentOS)..."
        if sudo -S dnf check-update < "${BECOME_PASSWORD_FILE}" || [ $? -eq 100 ]; then
            echo -e "${GREEN} Package lists updated successfully${NC}"
        else
            echo -e "${YELLOW} Package list update failed, continuing anyway${NC}"
        fi
    else
        echo -e "${YELLOW}Unknown package manager, skipping package list update${NC}"
    fi
    echo ""

    # Check if any critical dependencies are missing and handle appropriately
    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo -e "${RED}Missing critical system dependencies:${NC}"
        for dep in "${missing_deps[@]}"; do
            echo -e "${RED}  - $dep${NC}"
        done
        echo ""
        
        # Separate Python/pip issues, internet connectivity, and installable dependencies
        local python_issues=()
        local connectivity_issues=()
        local installable_deps=()
        
        for dep in "${missing_deps[@]}"; do
            if [[ "$dep" == "python3"* ]]; then
                python_issues+=("$dep")
            elif [[ "$dep" == "internet-connectivity" ]]; then
                connectivity_issues+=("$dep")
            else
                installable_deps+=("$dep")
            fi
        done
        
        # Handle internet connectivity issues first - EXIT IMMEDIATELY (cannot be auto-fixed)
        if [ ${#connectivity_issues[@]} -gt 0 ]; then
            echo -e "${RED}Critical connectivity requirements not met:${NC}"
            echo -e "${RED}  - Internet connectivity is required for:${NC}"
            echo -e "${RED}    * Pulling Docker images${NC}"
            echo -e "${RED}    * Downloading packages and dependencies${NC}"
            echo -e "${RED}    * Accessing container registries${NC}"
            echo -e "${RED}    * Cloning Git repositories${NC}"
            echo ""
            echo -e "${YELLOW}Please ensure internet connectivity and try again.${NC}"
            echo -e "${YELLOW}Common solutions:${NC}"
            echo -e "${YELLOW}  - Check network configuration${NC}"
            echo -e "${YELLOW}  - Verify firewall/proxy settings${NC}"
            echo -e "${YELLOW}  - Test: curl -I https://google.com${NC}"
            exit 1
        fi
        
        # Handle Python issues first - EXIT IMMEDIATELY (no user acknowledgment)
        if [ ${#python_issues[@]} -gt 0 ]; then
            echo -e "${RED}Critical Python requirements not met:${NC}"
            for issue in "${python_issues[@]}"; do
                echo -e "${RED}  - $issue${NC}"
            done
            echo ""
            echo -e "${YELLOW}Python 3.10+ is required for Enterprise Inference deployment.${NC}"
            echo -e "${YELLOW}Please install/configure Python 3.10+ and set python3_interpreter, then try again.${NC}"
            echo -e "${YELLOW}RHEL: dnf install python3 python3-pip${NC}"
            echo -e "${YELLOW}Ubuntu: apt update && apt install python3 python3-pip${NC}"
            exit 1
        fi
        
        # Handle installable dependencies (git, curl) with user acknowledgment
        if [ ${#installable_deps[@]} -gt 0 ]; then
            echo -e "${YELLOW}The following dependencies can be installed automatically:${NC}"
            for dep in "${installable_deps[@]}"; do
                echo -e "${YELLOW}  - $dep${NC}"
            done
            echo ""
            install_deps="yes"
            
            if [[ "$install_deps" =~ ^(yes|y|Y)$ ]]; then
                # Separate pip from other dependencies
                local pip_needed=false
                local other_deps=()
                
                for dep in "${installable_deps[@]}"; do
                    if [[ "$dep" == "pip" ]]; then
                        pip_needed=true
                    else
                        other_deps+=("$dep")
                    fi
                done
                
                # Install regular dependencies first (git, curl)
                if [ ${#other_deps[@]} -gt 0 ]; then
                    if command -v dnf &> /dev/null; then
                        echo "Installing dependencies using dnf RHEL..."
                        sudo -S dnf install -y "${other_deps[@]}" < "${BECOME_PASSWORD_FILE}"
                    elif command -v apt &> /dev/null; then
                        echo "Installing dependencies using apt Ubuntu..."
                        sudo -S apt update < "${BECOME_PASSWORD_FILE}" && sudo -S apt install -y "${other_deps[@]}" < "${BECOME_PASSWORD_FILE}"
                    else
                        echo -e "${RED}Unsupported package manager. This script supports RHEL (dnf) and Ubuntu (apt) only.${NC}"
                        echo -e "${YELLOW}Please install manually:${NC}"
                        echo -e "${YELLOW}  RHEL: dnf install ${other_deps[*]}${NC}"
                        echo -e "${YELLOW}  Ubuntu: apt install ${other_deps[*]}${NC}"
                        exit 1
                    fi
                fi
                
                # Install pip using system package manager if needed
                if [ "$pip_needed" = true ]; then
                    echo "Installing pip using system package manager..."
                    if command -v dnf &> /dev/null; then
                        python_version=$($python3_interpreter -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
                        if [[ "$python_version" == "3.11" ]]; then
                            echo "Installing python3.11-pip using dnf (RHEL 9)..."
                            if ! sudo -S dnf install -y python3.11-pip < "${BECOME_PASSWORD_FILE}"; then
                                echo -e "${RED}Failed to install python3.11-pip using dnf${NC}"
                                exit 1
                            fi
                        elif [[ "$python_version" == "3.12" ]]; then
                            echo "Installing python3.12-pip using dnf (RHEL 9)..."
                            if ! sudo -S dnf install -y python3.12-pip < "${BECOME_PASSWORD_FILE}"; then
                                echo -e "${RED}Failed to install python3.12-pip using dnf${NC}"
                                exit 1
                            fi
                        else
                            echo "Installing python3-pip using dnf (RHEL 9)..."
                            if ! sudo -S dnf install -y python3-pip < "${BECOME_PASSWORD_FILE}"; then
                                echo -e "${RED}Failed to install python3-pip using dnf${NC}"
                                exit 1
                            fi
                        fi
                    elif command -v apt &> /dev/null; then
                        echo "Installing python3-pip using apt (Ubuntu 22/24)..."
                        if ! sudo -S apt install -y python3-pip < "${BECOME_PASSWORD_FILE}"; then
                            echo -e "${RED}Failed to install python3-pip using apt${NC}"
                            exit 1
                        fi
                    else
                        echo -e "${RED}Unsupported system. This deployment only supports Ubuntu 22/24 and RHEL 9.4${NC}"
                        exit 1
                    fi
                fi
                
                # Verify installation
                local install_failed=()
                for dep in "${installable_deps[@]}"; do
                    if [[ "$dep" == "pip" ]]; then
                        if ! $python3_interpreter -m pip --version &> /dev/null; then
                            install_failed+=("$dep")
                        fi
                    else
                        if ! command -v "$dep" &> /dev/null; then
                            install_failed+=("$dep")
                        fi
                    fi
                done
                
                if [ ${#install_failed[@]} -gt 0 ]; then
                    echo -e "${RED}Failed to install: ${install_failed[*]}${NC}"
                    echo -e "${YELLOW}Please install them manually and try again.${NC}"
                    exit 1
                else
                    echo -e "${GREEN}All dependencies installed successfully!${NC}"
                fi
            else
                echo -e "${YELLOW}Installation cancelled. Please install the dependencies manually:${NC}"
                echo -e "${YELLOW}  RHEL: sudo dnf install ${installable_deps[*]}${NC}"
                echo -e "${YELLOW}  Ubuntu: sudo apt install ${installable_deps[*]}${NC}"
                exit 1
            fi
        fi
    fi
    
    echo -e "${GREEN}System prerequisites check completed successfully.${NC}"    
    return 0
}
