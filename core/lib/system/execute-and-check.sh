# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

execute_and_check() {
    local description=$1
    local command=$2
    local success_message=$3
    local failure_message=$4
    echo "$description"
    $command
    if [ $? -eq 0 ]; then
        echo "$success_message"
    else
        echo "$failure_message"
        exit 1
    fi
}