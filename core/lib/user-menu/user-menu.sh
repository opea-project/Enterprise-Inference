# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

update_drivers_and_firmware() {    
    echo "-------------------------------------------------"
    echo "|        Update Drivers and Firmware             |"
    echo "|------------------------------------------------|"
    echo "| 1) Update Drivers                              |"
    echo "| 2) Update Firmware                             |"
    echo "| 3) Update Both Drivers and Firmware            |"
    echo "|------------------------------------------------|"
    echo "Please choose an option (1, 2, or 3):"
    read -p "> " update_choice
    case $update_choice in
        1)
            update_gaudi_drivers
            ;;
        2)
            update_gaudi_firmware
            ;;
        3)
            update_gaudi_driver_and_firmware_both
            ;;
        *)
            echo "Invalid option. Please enter 1, 2, or 3."
            update_drivers_and_firmware
            ;;
    esac
}



manage_worker_nodes() {
    echo "-------------------------------------------------"
    echo "| Manage Worker Nodes                            |"
    echo "|------------------------------------------------|"
    echo "| 1) Add Worker Node                             |"
    echo "| 2) Remove Worker Node                          |"
    echo "|------------------------------------------------|"
    echo "Please choose an option (1 or 2):"
    read -p "> " worker_choice
    case $worker_choice in
        1)
            add_worker_node "$@"
            ;;
        2)
            remove_worker_node "$@"
            ;;
        *)
            echo "Invalid option. Please enter 1 or 2."
            manage_worker_nodes
            ;;
    esac
}



manage_models() {
    echo "-------------------------------------------------"
    echo "| Manage LLM Models                               "
    echo "|------------------------------------------------|"
    echo "| 1) Deploy Model                                |"
    echo "| 2) Undeploy Model                              |"
    echo "| 3) List Installed Models                       |"
    echo "| 4) Deploy Model from Hugging Face              |"
    echo "| 5) Remove Model using deployment name          |"
    echo "|------------------------------------------------|"
    echo "Please choose an option (1, 2, 3, or 4):"
    read -p "> " model_choice
    case $model_choice in
        1)
            add_model "$@"
            ;;
        2)
            remove_model "$@"
            ;;
        3)
            list_models "$@"
            ;;
        4)
            deploy_from_huggingface "$@"
            ;;
        5)
            remove_model_deployed_via_huggingface "$@"
            ;;
        *)
            echo "Invalid option. Please enter 1, 2, 3, or 4."
            manage_models
            ;;
    esac
}
