# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

read_config_file() {
    local config_file="$HOMEDIR/inventory/inference-config.cfg"
    if [ -f "$config_file" ]; then
        echo "Configuration file found, setting vars!"
        echo "---------------------------------------"
        while IFS='=' read -r key value || [ -n "$key" ]; do
            # Trim leading/trailing whitespace
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)
            # Skip empty lines and comments
            [[ -z "$key" || "$key" =~ ^#.* ]] && continue
            # Set the variable using a temporary file
            if [[ "$value" == "on" ]]; then
                value="yes"
            elif [[ "$value" == "off" ]]; then
                value="no"
            fi
            printf "%s=%s\n" "$key" "$value" >> temp_env_vars
        done < "$config_file"        
        
        # Load the environment variables from the temporary file
        source temp_env_vars        
        rm temp_env_vars    
        local metadata_config_file="$HOMEDIR/inventory/metadata/inference-metadata.cfg"
        if [ -f "$metadata_config_file" ]; then
            echo "Metadata configuration file found, setting vars!"
            echo "---------------------------------------"
            while IFS='=' read -r key value || [ -n "$key" ]; do
                key=$(echo "$key" | xargs)
                value=$(echo "$value" | xargs)
                # Skip empty lines and comments
                [[ -z "$key" || "$key" =~ ^#.* ]] && continue
                printf "%s=%s\n" "$key" "$value" >> temp_env_vars_metadata
            done < "$metadata_config_file"            
            source temp_env_vars_metadata
            rm temp_env_vars_metadata
        else
            echo "Enterprise Inference Metadata configuration file not found"
            exit 1        
        fi
                
        echo -n "place-holder-123" > "$HOMEDIR/inventory/.vault-passfile"
        vault_pass_file="$HOMEDIR/inventory/.vault-passfile"        

        INVENTORY_ALL_FILE="$HOMEDIR"/inventory/metadata/all.yml
        if [[ -n "$http_proxy" ]]; then
            sed -i -E "s|^[[:space:]]*#?[[:space:]]*http_proxy:.*|http_proxy: \"$http_proxy\"|" "$INVENTORY_ALL_FILE"
            sed -i -E "/^env_proxy:/,/^[^[:space:]]/s|^[[:space:]]*http_proxy:.*|  http_proxy: \"$http_proxy\"|" "$INVENTORY_ALL_FILE"
            export http_proxy
        fi

        if [[ -n "$https_proxy" ]]; then
            sed -i -E "s|^[[:space:]]*#?[[:space:]]*https_proxy:.*|https_proxy: \"$https_proxy\"|" "$INVENTORY_ALL_FILE"
            sed -i -E "/^env_proxy:/,/^[^[:space:]]/s|^[[:space:]]*https_proxy:.*|  https_proxy: \"$https_proxy\"|" "$INVENTORY_ALL_FILE"
            export https_proxy
        fi
                                
        if [[ -n "$no_proxy" ]]; then
            sed -i -E "/^env_proxy:/,/^[^[:space:]]/s|^[[:space:]]*no_proxy:.*|  no_proxy: \"$no_proxy\"|" "$INVENTORY_ALL_FILE"
            export no_proxy
        fi

        # Detect real upstream DNS servers from the host, skipping link-local (169.254.x.x)
        # and loopback (127.x.x.x) addresses that cause CoreDNS forwarding loops.
        # /run/systemd/resolve/resolv.conf is used when available (more reliable than /etc/resolv.conf
        # which may symlink to nodelocaldns or stub-resolver on systemd-resolved systems).
        local _resolv_src
        if [[ -f /run/systemd/resolve/resolv.conf ]]; then
            _resolv_src=/run/systemd/resolve/resolv.conf
        else
            _resolv_src=/etc/resolv.conf
        fi
        local _upstream_dns
        _upstream_dns=$(grep -E "^nameserver" "$_resolv_src" \
            | awk '{print $2}' \
            | grep -vE "^(127\.|169\.254\.)" \
            | head -3)
        if [[ -n "$_upstream_dns" ]]; then
            # Build the replacement lines for the upstream_dns_servers block.
            # The block already exists commented-out in all.yml; we uncomment it
            # and replace the placeholder IPs. Using sed keeps the block at its
            # original position and is safe to run repeatedly (idempotent).
            local _dns_list_sed
            _dns_list_sed=$(echo "$_upstream_dns" | awk 'BEGIN{ORS="\\n"} {printf "  - \"%s\"", $1}')

            # Step 1: uncomment the key line (handles both commented and already-active)
            sed -i -E 's|^#[[:space:]]*(upstream_dns_servers:.*)|\1|' "$INVENTORY_ALL_FILE"

            # Step 2: replace the entire list under upstream_dns_servers with detected IPs.
            # Matches all consecutive "  - ..." lines that follow the key and replaces them.
            python3 - "$INVENTORY_ALL_FILE" "$_upstream_dns" <<'PYEOF'
import sys
path = sys.argv[1]
servers = [s for s in sys.argv[2].split('\n') if s.strip()]
lines = open(path).readlines()
out, in_block = [], False
for line in lines:
    if line.startswith('upstream_dns_servers:'):
        out.append(line)
        for s in servers:
            out.append(f'  - "{s}"\n')
        in_block = True
        continue
    if in_block:
        # skip old list entries; stop skipping on any non-list line
        if line.startswith('  - ') or (line.strip() == '' and in_block):
            continue
        in_block = False
    out.append(line)
open(path, 'w').writelines(out)
PYEOF
        fi
        
        
        case "$device" in
            "cpu")
            device="cpu"
            deploy_habana_ai_operator="no"
            deploy_intel_gpu_plugin="no"
            ;;
            "hpu" | "gpu" | "gaudi2" | "gaudi3")
            if [[ "$device" == "gaudi2" || "$device" == "gpu" || "$device" == "hpu" ]]; then
                gaudi_platform="gaudi2"
                
            elif [[ "$device" == "gaudi3" ]]; then
                gaudi_platform="gaudi3"
            fi
            device="hpu"
            deploy_habana_ai_operator="yes"
            deploy_intel_gpu_plugin="no"
            ;;
            "xpu" | "bmg")
            device="xpu"
            deploy_habana_ai_operator="no"
            deploy_intel_gpu_plugin="yes"
            ;;
            *)
            echo "Invalid value for device. It should be 'cpu' for CPU, 'hpu', 'gpu', 'gaudi2', or 'gaudi3' for Gaudi GPU, or 'xpu' or 'bmg' for Intel Arc Battlemage GPU."
            exit 1
            ;;
        esac
        case "$deploy_keycloak_apisix" in
            "no")
                deploy_apisix="no"
                deploy_keycloak="no"                
                ;;
            "yes")
                deploy_apisix="yes"
                deploy_keycloak="yes"                
                ;;
            *)
                echo "Incorrect value for deploy_keycloak_apisix"
                exit 1
                ;;
        esac
        case "$deploy_genai_gateway" in
            "no")
                deploy_genai_gateway="no"                
                ;;
            "yes")
                deploy_genai_gateway="yes"                                
                ;;
            *)
                echo "Incorrect value for deploy_genai_gateway"
                exit 1
                ;;
        esac
        
        if [[ "$deploy_genai_gateway" == "yes" && "$deploy_keycloak_apisix" == "yes" ]]; then
            echo -e "${YELLOW}--------------------------------------------------------------------------${NC}"
            echo -e "${YELLOW}|  NOTICE:                                                                |${NC}"
            echo -e "${YELLOW}|  Both 'GenAI Gateway' and 'Keycloak & APISIX' cannot be enabled at      |${NC}"
            echo -e "${YELLOW}|  the same time.                                                         |${NC}"
            echo -e "${YELLOW}|  Please select either GenAI Gateway or Keycloak & APISIX                |${NC}"            
            echo -e "${YELLOW}--------------------------------------------------------------------------${NC}"
            exit 1
        fi


    else
        echo "Configuration file not found. Using default values or prompting for input."
    fi    
}
