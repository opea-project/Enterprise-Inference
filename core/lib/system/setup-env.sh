# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

setup_initial_env() {
    echo "Setting up the Initial Environment..."
    
    if [[ "$skip_check" != "true" ]]; then
        echo "Performing initial system prerequisites check..."
        if ! run_system_prerequisites_check; then
            echo "System prerequisites check failed. Please install missing dependencies and try again."
            exit 1
        fi
        echo "System prerequisites check completed successfully."
    else
        echo "Skipping system prerequisites check due to --skip-check argument."
    fi
        
    # In airgap mode, configure apt to use JFrog as the Debian/Ubuntu mirror
    # so Kubespray's apt update and apt install steps do not reach the internet.
    if [[ "$airgap_enabled" == "yes" ]] && command -v apt &> /dev/null; then
        echo "Configuring apt to use JFrog Artifactory as Debian mirror (airgap mode)..."
        local jfrog_apt_base="http://${jfrog_username}:${jfrog_password}@${jfrog_url#*://}/ei-debian-virtual"
        # Strip any trailing /artifactory double-path — jfrog_url already contains /artifactory
        jfrog_apt_base="http://${jfrog_username}:${jfrog_password}@$(echo "${jfrog_url}" | sed 's|^https\?://||')/ei-debian-virtual"
        sudo tee /etc/apt/sources.list > /dev/null << EOF
deb [trusted=yes] ${jfrog_apt_base} jammy main restricted universe multiverse
deb [trusted=yes] ${jfrog_apt_base} jammy-updates main restricted universe multiverse
deb [trusted=yes] ${jfrog_apt_base} jammy-security main restricted universe multiverse
EOF
        echo -e "${GREEN}apt configured to use JFrog at ${jfrog_url}/ei-debian-virtual${NC}"
        echo "Refreshing apt package lists from JFrog..."
        sudo apt-get update -qq
        echo -e "${GREEN}apt package lists updated from JFrog${NC}"
    fi

    if [[ -n "$https_proxy" ]]; then
        git config --global http.proxy "$https_proxy"
        git config --global https.proxy "$https_proxy"
    fi
    if [ ! -d "$KUBESPRAYDIR" ]; then
        if [[ "$airgap_enabled" == "yes" ]]; then
            echo "Downloading kubespray from JFrog Artifactory (airgap mode)..."
            kubespray_tarball="/tmp/kubespray.tar.gz"
            if curl -sf -u "${jfrog_username}:${jfrog_password}" \
                    -o "${kubespray_tarball}" \
                    "${jfrog_url}/ei-generic-binaries/kubespray.tar.gz"; then
                tar -xzf "${kubespray_tarball}" -C "$(dirname "$KUBESPRAYDIR")"
                if [ ! -d "$KUBESPRAYDIR" ]; then
                    echo -e "${RED}Failed to extract kubespray tarball — expected directory: $KUBESPRAYDIR${NC}"
                    exit 1
                fi
                cd $KUBESPRAYDIR
            else
                echo -e "${RED}----------------------------------------------------------------------------${NC}"
                echo -e "${RED}|  NOTICE: Failed to download Kubespray from JFrog.                        |${NC}"
                echo -e "${RED}|  Ensure kubespray.tar.gz is uploaded to ei-generic-binaries.             |${NC}"
                echo -e "${RED}----------------------------------------------------------------------------${NC}"
                exit 1
            fi
        else
            git clone https://github.com/kubernetes-sigs/kubespray.git $KUBESPRAYDIR
            if [ $? -ne 0 ] || [ ! -d "$KUBESPRAYDIR/.git" ]; then
                echo -e "${RED}----------------------------------------------------------------------------${NC}"
                echo -e "${RED}|  NOTICE: Failed to clone Kubespray Repository.                           |${NC}"
                echo -e "${RED}|  Unable to proceed with Inference Stack Deployment                        |${NC}"
                echo -e "${RED}|  due to missing dependency                                                |${NC}"
                echo -e "${RED}----------------------------------------------------------------------------${NC}"
                exit 1
            fi
            cd $KUBESPRAYDIR
            git checkout "$kubespray_version"
        fi
    else
        echo "Kubespray directory already exists, skipping clone."
        cd $KUBESPRAYDIR
    fi
    if [[ -n "$https_proxy" ]]; then
        git config --global --unset http.proxy
        git config --global --unset https.proxy
    fi
    
    VENVDIR="$KUBESPRAYDIR/venv"
    REMOTEDIR="/tmp/helm-charts"    
    if [ ! -d "$VENVDIR" ]; then                
        if [[ "$airgap_enabled" != "yes" ]]; then
            echo "Installing python3-venv package..."
            if command -v apt &> /dev/null; then
                python_version=$($python3_interpreter -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
                sudo apt install -y python${python_version}-venv || sudo apt install -y python3-venv
            fi
        fi                
        if [[ "$airgap_enabled" == "yes" ]]; then
            # In airgap mode ensurepip is unavailable (python3-pip-whl not installed).
            # Create the venv without pip, then bootstrap pip from the JFrog wheel.
            if ! $python3_interpreter -m venv --without-pip $VENVDIR; then
                echo -e "${RED}Failed to create virtual environment.${NC}"
                exit 1
            fi
            echo "Virtual environment created (without-pip). Bootstrapping pip from JFrog..."
            local pip_whl_url="${jfrog_url}/ei-generic-binaries/pip.whl"
            local tmp_pip_whl="/tmp/pip-bootstrap.whl"
            if ! curl -f -s -u "${jfrog_username}:${jfrog_password}" \
                    -o "$tmp_pip_whl" "$pip_whl_url" 2>/dev/null; then
                echo -e "${RED}Failed to download pip wheel from JFrog at ${pip_whl_url}${NC}"
                exit 1
            fi
            # Rename to proper wheel filename using metadata inside the zip
            proper_name=$($python3_interpreter -c "
import zipfile, sys
try:
    z = zipfile.ZipFile('$tmp_pip_whl')
    wf = next(x for x in z.namelist() if x.endswith('.dist-info/WHEEL'))
    base = wf.split('/')[0].replace('.dist-info', '')
    meta = {}
    for line in z.read(wf).decode().splitlines():
        if ': ' in line:
            k, v = line.split(': ', 1)
            meta[k] = v
    tag = meta.get('Tag', 'py3-none-any')
    print(f'{base}-{tag}.whl')
except Exception as e:
    sys.exit(1)
" 2>/dev/null)
            if [ -n "$proper_name" ]; then
                mv "$tmp_pip_whl" "/tmp/$proper_name"
                tmp_pip_whl="/tmp/$proper_name"
            fi
            if ! PYTHONPATH="$tmp_pip_whl" $VENVDIR/bin/python3 -m pip install \
                    --no-index "$tmp_pip_whl"; then
                echo -e "${RED}Failed to bootstrap pip inside virtual environment.${NC}"
                exit 1
            fi
            echo "pip bootstrapped successfully inside virtual environment."
        else
            if ! $python3_interpreter -m venv $VENVDIR; then
                echo -e "${RED}Failed to create virtual environment.${NC}"
                exit 1
            fi
        fi
        echo "Virtual environment created within Kubespray directory."
    else
        echo "Virtual environment already exists within Kubespray directory, skipping creation."
    fi
    source $VENVDIR/bin/activate
    echo "Attempting to activate the virtual environment..."    
    if [ -z "$VIRTUAL_ENV" ]; then        
        rm -rf "$KUBESPRAYDIR"
        echo -e "${RED}----------------------------------------------------------------------------${NC}"
        echo -e "${RED}|  NOTICE: Failed to activate the virtual environment.                      |${NC}"
        echo -e "${RED}|  Please retrigger the Inference Stack Deployment                          |${NC}"
        echo -e "${RED}|                                                                           |${NC}"
        echo -e "${RED}----------------------------------------------------------------------------${NC}"
        exit 1
    else
        echo "Virtual environment activated successfully. Path: $VIRTUAL_ENV"
    fi                 
        
    export PIP_BREAK_SYSTEM_PACKAGES=1
    if [[ "$airgap_enabled" == "yes" ]]; then
        jfrog_pip_index="${jfrog_url}/api/pypi/ei-pypi-virtual/simple"
        jfrog_host="${jfrog_url#*://}"
        jfrog_host="${jfrog_host%%/*}"
        pip_extra_args="--index-url http://${jfrog_username}:${jfrog_password}@${jfrog_host}/artifactory/api/pypi/ei-pypi-virtual/simple --trusted-host ${jfrog_host}"
        $VENVDIR/bin/python3 -m pip install --upgrade pip $pip_extra_args
        $VENVDIR/bin/python3 -m pip install -U -r requirements.txt $pip_extra_args
    else
        $VENVDIR/bin/python3 -m pip install --upgrade pip
        $VENVDIR/bin/python3 -m pip install -U -r requirements.txt
    fi
    
    echo "Verifying Ansible Installation..."
    if $VENVDIR/bin/python3 -c "import ansible" &> /dev/null; then
        echo -e "${GREEN} Ansible installed successfully${NC}"
    else
        echo -e "${RED}----------------------------------------------------------------------------${NC}"
        echo -e "${RED}|  NOTICE: Ansible Installation Failed.                                     |${NC}"        
        echo -e "${RED}|  Unable to proceed with Inference Stack Deployment                        |${NC}"        
        echo -e "${RED}|  due to missing dependency                                                |${NC}"        
        echo -e "${RED}----------------------------------------------------------------------------${NC}"        
        exit 1
    fi    

    echo -e "${GREEN} Enterprise Inference requirements installed.${NC}"
    cp -r "$HOMEDIR"/helm-charts "$HOMEDIR"/scripts "$KUBESPRAYDIR"/
    cp -r "$KUBESPRAYDIR"/inventory/sample/ "$KUBESPRAYDIR"/inventory/mycluster
    cp  "$HOMEDIR"/inventory/hosts.yaml $KUBESPRAYDIR/inventory/mycluster/
    cp "$HOMEDIR"/inventory/metadata/addons.yml $KUBESPRAYDIR/inventory/mycluster/group_vars/k8s_cluster/addons.yml    
    cp "$HOMEDIR"/playbooks/* "$KUBESPRAYDIR"/playbooks/    
    gaudi2_values_file_path="$REMOTEDIR/vllm/gaudi-values.yaml"
    gaudi3_values_file_path="$REMOTEDIR/vllm/gaudi3-values.yaml"
    xeon_values_file_path="$REMOTEDIR/vllm/xeon-values.yaml"
    cp "$HOMEDIR"/inventory/metadata/addons.yml $KUBESPRAYDIR/inventory/mycluster/group_vars/k8s_cluster/addons.yml
    cp "$HOMEDIR"/inventory/metadata/all.yml $KUBESPRAYDIR/inventory/mycluster/group_vars/all/all.yml
    if [[ "$airgap_enabled" == "yes" ]] && [ -f "$HOMEDIR/inventory/metadata/offline.yml" ]; then
        cp "$HOMEDIR"/inventory/metadata/offline.yml $KUBESPRAYDIR/inventory/mycluster/group_vars/all/offline.yml
        # Replace any hardcoded IP:8082 in the copied files with the actual JFrog
        # host from jfrog_url, so the repo can be reused across environments without
        # manual IP edits
        local _jfrog_host
        _jfrog_host=$(echo "$jfrog_url" | sed 's|https\?://||' | sed 's|/.*||')
        # Replace placeholder (fresh copies) AND any stale real IP (reruns after JFrog IP change)
        for _f in "$KUBESPRAYDIR/inventory/mycluster/group_vars/all/all.yml" \
                   "$KUBESPRAYDIR/inventory/mycluster/group_vars/all/offline.yml"; do
            sed -i "s|JFROG_HOST:8082|$_jfrog_host|g" "$_f"
            sed -i -E "s|[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:8082|$_jfrog_host|g" "$_f"
        done
        # Inject JFrog credentials into files_repo so Kubespray can authenticate
        # when downloading binaries (anonymous access is not enabled for generic repos)
        sed -i "s|files_repo: \"http://|files_repo: \"http://${jfrog_username}:${jfrog_password}@|g" \
            "$KUBESPRAYDIR/inventory/mycluster/group_vars/all/offline.yml"
        # If credentials were already injected on a prior run the pattern above won't match.
        # Normalise by replacing the credentialled URL to ensure the current password is used.
        sed -i "s|files_repo: \"http://[^@]*@[0-9.]*:[0-9]*/artifactory|files_repo: \"http://${jfrog_username}:${jfrog_password}@${_jfrog_host}/artifactory|g" \
            "$KUBESPRAYDIR/inventory/mycluster/group_vars/all/offline.yml"
    fi
    # In airgap mode, force kube_version in k8s_cluster group_vars to match the version
    # cached in JFrog. group_vars/k8s_cluster/ has higher Ansible precedence than
    # group_vars/all/ so offline.yml's kube_version pin is silently ignored without this.
    if [[ "$airgap_enabled" == "yes" ]]; then
        local _k8s_cluster_yml="$KUBESPRAYDIR/inventory/mycluster/group_vars/k8s_cluster/k8s-cluster.yml"
        local _kube_ver
        _kube_ver=$(grep '^kube_version:' "$HOMEDIR/inventory/metadata/offline.yml" 2>/dev/null | awk '{print $2}')
        if [ -n "$_kube_ver" ] && [ -f "$_k8s_cluster_yml" ]; then
            if grep -q "^kube_version:" "$_k8s_cluster_yml"; then
                sed -i "s|^kube_version:.*|kube_version: ${_kube_ver}|" "$_k8s_cluster_yml"
            else
                echo "kube_version: ${_kube_ver}" >> "$_k8s_cluster_yml"
            fi
            echo "Pinned kube_version: ${_kube_ver} in k8s_cluster group_vars (airgap mode)"
        fi
    fi

    # In airgap mode, patch containerd hosts.toml.j2 so every mirror host includes
    # Basic auth credentials. containerd's anonymous Bearer token flow fails when
    # JFrog anonymous access is restricted — injecting credentials directly bypasses it.
    if [[ "$airgap_enabled" == "yes" ]]; then
        local _tmpl="$KUBESPRAYDIR/roles/container-engine/containerd/templates/hosts.toml.j2"
        if [ -f "$_tmpl" ] && ! grep -q "jfrog_username" "$_tmpl"; then
            echo "Patching containerd hosts.toml.j2 with JFrog auth header (airgap mode)..."
            cat > /tmp/patch_hosts_toml.py << 'PYEOF'
import sys
path = sys.argv[1]
content = open(path).read()
auth_block = (
    "{%- if airgap_enabled | default(false) | bool and jfrog_username is defined and jfrog_username != '' %}\n"
    "  [host.\"{{ mirror.host }}\".header]\n"
    "    Authorization = [\"Basic {{ (jfrog_username + ':' + jfrog_password) | b64encode }}\"]\n"
    "{%- endif %}\n"
)
for marker in ('{%- endfor %}', '{% endfor %}'):
    idx = content.rfind(marker)
    if idx != -1:
        content = content[:idx] + auth_block + content[idx:]
        open(path, 'w').write(content)
        print(f"Patched {path} with JFrog auth header")
        break
else:
    print(f"WARNING: endfor not found in {path} — skipping patch")
PYEOF
            python3 /tmp/patch_hosts_toml.py "$_tmpl"
        else
            [ ! -f "$_tmpl" ] && echo -e "${YELLOW}hosts.toml.j2 not found at $_tmpl — skipping auth patch${NC}"
        fi
    fi

    cp -r "$HOMEDIR"/roles/* $KUBESPRAYDIR/roles/

    mkdir -p "$KUBESPRAYDIR/config"        
    chmod +x $HOMEDIR/scripts/generate-vault-secrets.sh

    # Only generate vault secrets if vault.yml doesn't exist or is incomplete
    vault_file="$HOMEDIR/inventory/metadata/vault.yml"
    mandatory_keys=("litellm_master_key" "litellm_salt_key" "redis_password" "langfuse_secret_key" "langfuse_public_key" "postgresql_username" "postgresql_password" "clickhouse_username" "clickhouse_password" "langfuse_login" "langfuse_user" "langfuse_password" "minio_secret" "minio_user" "postgres_user" "postgres_password")

    if [ ! -f "$vault_file" ]; then
        echo "vault.yml not found at $vault_file, generating vault secrets..."
        bash $HOMEDIR/scripts/generate-vault-secrets.sh
    else
        echo "Checking vault.yml for mandatory keys..."
        missing_keys=()
        for key in "${mandatory_keys[@]}"; do
            if ! grep -q "^${key}:" "$vault_file"; then
                missing_keys+=("$key")
            fi
        done

        if [ ${#missing_keys[@]} -gt 0 ]; then
            echo -e "${YELLOW}vault.yml exists but is missing mandatory keys: ${missing_keys[*]}${NC}"
            echo "Regenerating vault.yml with all mandatory keys..."
            bash $HOMEDIR/scripts/generate-vault-secrets.sh
        else
            echo -e "${GREEN}vault.yml exists and contains all mandatory keys. Skipping generation...${NC}"
        fi
    fi

    if [ "$purge_inference_cluster" != "purging" ]; then        
        if [[ "$deploy_llm_models" == "yes" || "$deploy_keycloak_apisix" == "yes" || "$deploy_genai_gateway" == "yes" || "$deploy_observability" == "yes" || "$deploy_logging" == "yes" || "$deploy_ceph" == "yes" || "$deploy_istio" == "yes" || "$deploy_finetune_plugin" == "yes" ]]; then
            if [ ! -s "$HOMEDIR/inventory/metadata/vault.yml" ]; then                
                echo -e "${YELLOW}----------------------------------------------------------------------------${NC}"
                echo -e "${YELLOW}|  NOTICE: inventory/metadata/vault.yml is empty!                           |${NC}"
                echo -e "${YELLOW}|  Please refer to docs/configuring-vault-values.md for instructions on     |${NC}"
                echo -e "${YELLOW}|  updating vault.yml                                                       |${NC}"
                echo -e "${YELLOW}----------------------------------------------------------------------------${NC}"
                exit 1
            fi      
        fi          
    fi    
    cp "$HOMEDIR"/inventory/metadata/vault.yml $KUBESPRAYDIR/config/vault.yml            
    mkdir -p "$KUBESPRAYDIR/config/vars" 
    cp -r "$HOMEDIR"/inventory/metadata/vars/* $KUBESPRAYDIR/config/vars/    
    cp "$HOMEDIR"/playbooks/* "$KUBESPRAYDIR"/playbooks/
    echo "Additional files and directories copied to Kubespray directory."
        
    if [[ "$skip_check" != "true" ]]; then
        echo "Performing infrastructure readiness check..."
        if ! run_infrastructure_readiness_check; then
            echo "Infrastructure readiness check failed. Please resolve the issues and try again."
            exit 1
        fi
    else
        echo "Skipping infrastructure readiness check due to --skip-check argument."
    fi
    echo "Infrastructure readiness check completed successfully."    
    gaudi2_values_file_path="$REMOTEDIR/vllm/gaudi-values.yaml"
    gaudi3_values_file_path="$REMOTEDIR/vllm/gaudi3-values.yaml"
    if [[ "$airgap_enabled" == "yes" ]]; then
        echo "Installing Ansible collections from JFrog Artifactory (airgap mode)..."
        for coll_entry in "kubernetes-core:kubernetes.core" "ansible-posix:ansible.posix" "community-kubernetes:community.kubernetes" "community-general:community.general"; do
            coll_file="${coll_entry%%:*}"
            coll_name="${coll_entry##*:}"
            tarball_url="${jfrog_url}/ei-generic-binaries/ansible-collections/${coll_file}-latest.tar.gz"
            tmp_file="/tmp/${coll_file}.tar.gz"
            echo "Installing ${coll_name} from JFrog..."
            if curl -sf -u "${jfrog_username}:${jfrog_password}" -o "${tmp_file}" "${tarball_url}"; then
                ansible-galaxy collection install "${tmp_file}" --force
            else
                echo -e "${YELLOW}Warning: ${coll_name} not found in JFrog at ${tarball_url} — skipping${NC}"
            fi
        done
    else
        ansible-galaxy collection install kubernetes.core community.general ansible.posix
    fi
}


invoke_prereq_workflows() {
    if [ $prereq_executed -eq 0 ]; then
        read_config_file "$@"
        if [ -z "$cluster_url" ] || [ -z "$cert_file" ] || [ -z "$key_file" ] || [ -z "$keycloak_client_id" ] || [ -z "$keycloak_admin_user" ] || [ -z "$keycloak_admin_password" ]; then
            echo "Some required arguments are missing. Prompting for input..."
            prompt_for_input
        fi
        setup_initial_env "$@"
        # Set the flag to 1 (executed)
        prereq_executed=1
    else
        echo "Prerequisites have already been executed. Skipping..."
    fi
}

install_ansible_collection() {
    echo "Installing community.general collection..."
    ansible-galaxy collection install community.general
}
