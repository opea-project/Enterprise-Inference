# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

update_cluster() {          
    echo "-------------------------------------------------"
    echo "|             Update Existing Cluster            |"
    echo "|------------------------------------------------|"
    echo "| 1) Manage Worker Nodes                         |"
    echo "| 2) Manage LLM Models                           |"
    #echo "| 3) Update Driver and Firmware                  |"
    echo "|------------------------------------------------|"    
    echo "Please choose an option (1 or 2):"
    read -p "> " update_choice
    case $update_choice in
        1)
            manage_worker_nodes "$@"
            ;;
        2)
            manage_models "$@"
            ;;
        # 3)
        #     update_drivers_and_firmware "$@"
        #     ;;
        *)
            echo "Invalid option. Please enter 1 or 2."
            update_cluster
            ;;
    esac
}