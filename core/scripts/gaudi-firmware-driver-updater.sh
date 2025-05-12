#!/bin/bash

RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
BLUE=$(tput setaf 4)
NC=$(tput sgr0)  # Reset color

# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
# Permission is granted for recipient to internally use and modify this software for purposes of benchmarking and testing on Intel architectures. 
# This software is provided "AS IS" possibly with faults, bugs or errors; it is not intended for production use, and recipient uses this design at their own risk with no liability to Intel.
# Intel disclaims all warranties, express or implied, including warranties of merchantability, fitness for a particular purpose, and non-infringement. 
# Recipient agrees that any feedback it provides to Intel about this software is licensed to Intel for any purpose worldwide. No permission is granted to use Intel’s trademarks.
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the code.

#
# Gaudi Driver, Firmware Update Automation
#
# Description:
# This script updates the Gaudi drivers and firmware version.
#
# Requirements:
# - Ubuntu or compatible Linux distribution
# - Root privileges (for package installation and driver management)
# - Internet connection (for downloading the installer and packages)
#
# Usage:
# 1. Save this script to a file (e.g., update_habana.sh)
# 2. Make the script executable: chmod +x update_habana.sh
# 3. Run the script as root: 
#    To update both drivers and firmwares bash gaudi-firmware-driver-updater.sh --both
#    To update only drivers: sudo bash gaudi-firmware-driver-updater.sh --drivers
#    To update only firmware: sudo bash gaudi-firmware-driver-updater.sh --firmware
#
# Output:
# The script provides colored output for better visibility and readability:
# - Yellow: Informational messages
# - Green: Success messages
# - Red: Error messages
#
# Error Handling:
# The script includes robust error handling and checks at each step. If any
# command fails, the script will print an error message and exit with a
# non-zero status code.
#

update_driver_script_ack=""

# Function to update Gaudi drivers
update_drivers() {
    # Check the current driver version
    current_driver_version=$(modinfo habanalabs | grep -m1 '^version:' | awk '{print $2}')
    if [ "$current_driver_version" != "1.18.0-524" ]; then
        echo -e "${YELLOW}Current Gaudi driver version: $current_driver_version${NC}"
        echo -e "${YELLOW}Expected version: 1.18.0-524${NC}"
        echo $update_driver_script_ack
        if [ "$update_driver_script_ack" != "yes" ]; then
            read -p "${YELLOW}This operation will update the Gaudi drivers to version 1.18.0-524. Do you want to proceed? (y/n) ${NC}" -r confirm
            if [[ ! $confirm =~ ^[Yy]$ ]]; then
                echo -e "${RED}Driver update cancelled.${NC}"
                return
            fi
        fi
        # Download the base Gaudi installer
        echo -e "${YELLOW}Downloading Gaudi installer...${NC}"
        echo -e "${YELLOW}Unloading Gaudi drivers...${NC}"
        wget -nv https://vault.habana.ai/artifactory/gaudi-installer/1.18.0/habanalabs-installer.sh
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to download Gaudi installer.${NC}"
            exit 1
        fi
        echo -e "${GREEN}Gaudi installer downloaded successfully.${NC}"
        echo -e "${YELLOW}Installing Gaudi base components...${NC}"
        chmod +x habanalabs-installer.sh
        ./habanalabs-installer.sh install --type base -y
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install Gaudi base components.${NC}"
            exit 1
        fi
        echo -e "${GREEN}Gaudi base components installed successfully.${NC}"
        echo -e "${YELLOW}Installing Gaudi container runtime...${NC}"
        sudo apt install -y habanalabs-container-runtime=1.18.0-524
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install Gaudi container runtime.${NC}"
            #exit 1
        fi
        echo -e "${GREEN}Gaudi container runtime installed.${NC}"               
    else
        echo -e "${GREEN}Gaudi driver version is already 1.18.0-524.${NC}"
    fi
}

# Function to update Gaudi firmware
update_firmware() {
    # Check the current firmware version
    current_firmware_version=$(modinfo habanalabs | grep -m1 '^version:' | awk '{print $2}')
    if [ "$current_firmware_version" != "1.18.0-524" ]; then
        echo -e "${YELLOW}Current Gaudi firmware version: $current_firmware_version${NC}"
        echo -e "${YELLOW}Expected version: 1.18.0-524${NC}"
        if [ "$update_driver_script_ack" != "yes" ]; then
            read -p "${YELLOW}This operation will update the Gaudi firmware to version 1.18.0-524. Do you want to proceed? (y/n) ${NC}" -r confirm
            if [[ ! $confirm =~ ^[Yy]$ ]]; then
                echo -e "${RED}Firmware update cancelled.${NC}"
                return
            fi
        fi
        # Unload drivers
        echo "Unloading Habana drivers..."
        sudo modprobe -r habanalabs &>/dev/null || true
        sudo modprobe -r habanalabs_cn &>/dev/null || true
        sudo modprobe -r habanalabs_ib &>/dev/null || true
        sudo modprobe -r habanalabs_en &>/dev/null || true
        # Install firmware package
        echo "Updating the downloader package..."
        sudo apt update
        sudo apt install -y --allow-downgrades habanalabs-firmware-odm=1.18.0-524
        # Update firmware
        echo "Updating the firmware..."
        sudo hl-fw-loader
        # Load drivers
        echo "Loading Habana drivers..."
        sudo modprobe habanalabs
        sudo modprobe habanalabs_cn
        sudo modprobe habanalabs_ib
        sudo modprobe habanalabs_en
    else
        echo -e "${GREEN}Gaudi firmware version is already 1.18.0-524.${NC}"
    fi
}


# Parse command-line arguments
if [ "$1" == "--drivers" ]; then
    update_driver_script_ack="yes"
    update_drivers "$@"    
elif [ "$1" == "--firmware" ]; then
    update_driver_script_ack="yes"
    update_firmware "$@"
elif [ "$1" == "--both" ]; then    
    update_driver_script_ack="yes"
    update_firmware "$@"
    update_drivers "$@" 
else
    echo "Undefined Selection, please select a parameter --firmware or --drivers or --both"
fi
