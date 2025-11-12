# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0



update_gaudi_drivers() {
    read -p "WARNING: Updating Gaudi drivers may cause system downtime. Do you want to proceed? (yes/no) " -r
    echo
    if [[ $REPLY =~ ^(yes|y|Y)$ ]]; then
        echo "Initiating Gaudi driver update process..."
        execute_and_check "Deploying Drivers..." update_drivers \
                        "Gaudi Driver updated successfully. Please reboot the machine for changes to take effect." \
                        "Failed to update Gaudi driver. Exiting."
    else
        echo "Gaudi driver update cancelled."
    fi
}
update_gaudi_firmware() {
    read -p "WARNING: Updating Gaudi firmware may cause system downtime. Do you want to proceed? (yes/no) " -r
    echo
    if [[ $REPLY =~ ^(yes|y|Y)$ ]]; then
        echo "Initiating Gaudi firmware update process..."
        execute_and_check "Deploying Firmware..." update_firmware \
                        "Gaudi Firmware updated successfully. Please reboot the machine for changes to take effect." \
                        "Failed to update Gaudi Firmware. Exiting."
    else
        echo "Gaudi firmware update cancelled."
    fi
}
update_gaudi_driver_and_firmware_both() {
    read -p "WARNING: Updating Gaudi drivers and firmware may cause system downtime. Do you want to proceed? (yes/no) " -r
    echo
    if [[ $REPLY =~ ^(yes|y|Y)$ ]]; then
        echo "Initiating Gaudi driver and firmware update process..."
        execute_and_check "Deploying Driver,Firmware..." update_drivers_and_firmware_both \
                        "Gaudi Driver,Firmware updated successfully. Please reboot the machine for changes to take effect." \
                        "Failed to update Gaudi Driver,Firmware. Exiting."
    else
        echo "Gaudi driver and firmware update cancelled."
    fi
}

# Update drivers
update_drivers() {
    invoke_prereq_workflows
    echo "${YELLOW}Updating drivers...${NC}"
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-gaudi-firmware-driver.yml \
        --extra-vars "update_type=drivers"
    echo "${GREEN}Drivers updated successfully!${NC}"
}

# Update firmware
update_firmware() {
    invoke_prereq_workflows
    echo "${YELLOW}Updating firmware...${NC}"
    ansible-playbook -i "${INVENTORY_PATH}" playbooks/deploy-gaudi-firmware-driver.yml \
        --extra-vars "update_type=firmware"
    echo "${GREEN}Firmware updated successfully!${NC}"
}

# Update both drivers and firmware
update_drivers_and_firmware_both() {
    update_drivers
    update_firmware
}