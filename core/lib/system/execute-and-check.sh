# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# shellcheck shell=bash

execute_and_check() {
    local description=$1
    local command=$2
    local success_message=$3
    local failure_message=$4
    echo "$description"
    if $command; then
        echo "$success_message"
    else
        echo "$failure_message"
        exit 1
    fi
}