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
        
        
        case "$cpu_or_gpu" in
            "c" | "cpu")
            cpu_or_gpu="c"
            deploy_habana_ai_operator="no"
            ;;
            "g" | "gpu" | "gaudi2" | "gaudi3")
            if [[ "$cpu_or_gpu" == "gaudi2" || "$cpu_or_gpu" == "gpu" || "$cpu_or_gpu" == "g" ]]; then
                gaudi_platform="gaudi2"
                
            elif [[ "$cpu_or_gpu" == "gaudi3" ]]; then
                gaudi_platform="gaudi3"
            fi
            cpu_or_gpu="g"
            deploy_habana_ai_operator="yes"            
            ;;
            *)
            echo "Invalid value for cpu_or_gpu. It should be 'c' or 'cpu' for CPU, or 'g', 'gpu', 'gaudi2', or 'gaudi3' for GPU."
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
