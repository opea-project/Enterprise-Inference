# Setup Single Node Gaudi Using Ansible

This playbook sets up a single node Gaudi inference environment using Ansible. It is designed to be run on the Gaudi node where the Intel® AI for Enterprise Inference Service will be deployed. The playbook installs all necessary dependencies, configures the environment, and prepares the system for the Intel® AI for Enterprise Inference Service. You will need to have the Gaudi drivers and firmware installed on the system before running this playbook, for more information on installing the Gaudi drivers and firmware, refer to the [Gaudi Drivers Installation Guide](https://github.com/opea-project/Enterprise-Inference/blob/main/core/catalog/docs/gaudi/gaudi-prerequisites.md).

Many of the defaults are setup to work out of the box, but you will need to update the **`cluster_ip`** and provide the **`hf_token`** for downloading models from Hugging Face.

There is also a template directory that contains a set of templates for the various configuration files that are used by the AI Inference Service. These templates are used to generate the final configuration files based on the variables defined in the playbook. Do not modify these files directly.

## Variables to Update in `einf-singlenode-gaudi.yml`

Before running the playbook, review and update the following variables in the `einf-singlenode-gaudi.yml` file to match your environment:

### General Configuration
- **`cluster_url`**: The DNS name for the cluster. Update this to the desired hostname (e.g., `api.example.com`).
- **`cluster_ip`**: The IP address of the node where the playbook will run.
- **`ai_user`**: The username for the Enterprise Inference Service. Change this if you want to use a different user.

### Keycloak Configuration (ignore if not using Keycloak)
- **`keycloak_client_id`**: The client ID for Keycloak.
- **`keycloak_admin_user`**: The Keycloak admin username.
- **`keycloak_admin_password`**: The Keycloak admin password. Update this to a secure password.

### Hugging Face Tokens
- **`hf_token`**: Your Hugging Face token for downloading models.
- **`hf_token_falcon3`**: Hugging Face token for Falcon 3. This can be the same as `hf_token`.

### Model Configuration
- **`models`**: A comma-separated list of model IDs to deploy (e.g., `1,2`). See the main documentation for a list of the models. The current setup only allows for one model to be deployed at a time.
- **`cpu_or_gpu`**: Set to `cpu` or `gpu` depending on the hardware.

### Certificate Configuration
- **`cert_dir`**: The directory where certificates will be stored. No need to update it.
- **`cert_validity_days`**: The number of days the certificate will be valid.
- **`cert_country`**, **`cert_state`**, **`cert_locality`**, **`cert_organization`**, **`cert_organizational_unit`**, **`cert_email`**: Update these fields to match your organization’s details.

### Paths
- **`einf_path`**: The path where the Enterprise Inference Service files will be extracted. Update this if the default path does not suit your environment.

### Deployment Configuration
These settings are all set to `on` by default in the playbook, change these variables if a component isn't needed, typically you don't need to worry about these settings.

- **`deploy_kubernetes_fresh`**: Set to `on` or `off` to enable or disable fresh Kubernetes deployment.
- **`deploy_ingress_controller`**: Set to `on` or `off` to enable or disable the ingress controller.
- **`deploy_keycloak_apisix`**: Set to `on` or `off` to enable or disable Keycloak with APISIX.
- **`deploy_observability`**: Set to `on` or `off` to enable or disable observability tools.



## How to Run the Playbook

1. **Install Ansible**  
   
   Ensure Ansible is installed on your system. You can install it using the following command:

   ```bash
   sudo apt update && sudo apt install -y ansible
   ```

2. **Run the Playbook**
   
   Execute the playbook using the following command:

   ```bash
   git clone https://github.com/opea-project/Enterprise-Inference.git
   cd Enterprise-Inference/docs/examples/single-node-gaudi
   sudo ansible-playbook einf-singlenode-gaudi.yml
   ```

3. **Wait for the playbook to complete**
   
   The playbook will take some time to run as it installs and configures all the necessary components. The final task in the playbook, `Run the AI Inference Service installation script` may take up to 25 minutes to complete, depending on the number of models being deployed. The output of the script will be displayed in the terminal once it is complete.

>*Ensure the system has access to the internet to download required packages and dependencies. Review the playbook for any additional configurations specific to your environment.*

>*If you encounter any issues, check the Ansible logs for detailed error messages.*

## Post Playbook

After the playbook has completed successfully, the models may take some time to be ready. Below are some commands to check the status of the services and pods deployed as part of the playbook.

### Kubectl Commands

To see the services deployed as part of the playbook, run `sudo kubectl get services`.

```bash
$ sudo kubectl get services
NAME                     TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
keycloak                 ClusterIP   10.233.36.216   <none>        80/TCP     71m
keycloak-headless        ClusterIP   None            <none>        8080/TCP   71m
keycloak-metrics         ClusterIP   10.233.42.120   <none>        8080/TCP   71m
keycloak-postgresql      ClusterIP   10.233.45.219   <none>        5432/TCP   71m
keycloak-postgresql-hl   ClusterIP   None            <none>        5432/TCP   71m
kubernetes               ClusterIP   10.233.0.1      <none>        443/TCP    81m
vllm-llama-8b-service    ClusterIP   10.233.3.145    <none>        80/TCP     63m
```

To see the status of the pods, run the command `sudo kubectl get pods --all-namespaces`. The pods that contain the models can take awhile to be ready. This is an example of the output of this command, showing a portion of the output. You can see in this example that the `vllm-llama-8b-69b864d856-9wb95` pod is not ready yet. The `READY` column shows the number of containers that are ready out of the total number of containers in the pod. In this case, it shows `0/1`, which means that the pod is not ready yet. The VLLM service is still starting.

```bash
kubectl get pods --all-namespaces
NAMESPACE            NAME                                                     READY   STATUS    RESTARTS   AGE
auth-apisix          auth-apisix-787bc7cb4d-9cqrx                             1/1     Running   0          72m
auth-apisix          auth-apisix-etcd-0                                       1/1     Running   0          72m
auth-apisix          auth-apisix-ingress-controller-5c9c5459fb-r4svk          1/1     Running   0          72m
default              keycloak-0                                               1/1     Running   0          78m
default              keycloak-postgresql-0                                    1/1     Running   0          78m
default              vllm-llama-8b-69b864d856-9wb95                           0/1     Running   0          70m
```

To see the logs of a specific pod, run the command `sudo kubectl logs <pod_name>`. For example, to see the logs of the `vllm-llama-8b-69b864d856-9wb95` pod, run:

```bash
sudo kubectl logs vllm-llama-8b-69b864d856-9wb95
```
This will show the logs of the pod, which can be useful for debugging any issues that may arise during the deployment process.

>If you see a pod that is crashing frequently, check the logs of that pod. One frequent issue is that the Hugging Face token used doesn't have access to the model. If this is happening, you will see an error message like `Cannot access gated repo for url https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3/resolve/main/config.json`. This means that the token used does not have access to the model. You can either update the token or use a different model that is not gated.

### Testing the API
On the Node run the following commands to test the successful deployment of Intel® AI for Enterprise Inference

```
export USER=api-admin
export PASSWORD=changeme!!
export BASE_URL=https://api.example.com
export KEYCLOAK_REALM=master
export KEYCLOAK_CLIENT_ID=api
export KEYCLOAK_CLIENT_SECRET=$(bash ~/core/scripts/keycloak-fetch-client-secret.sh api.example.com api-admin 'changeme!!' api | awk -F': ' '/Client secret:/ {print $2}')
export TOKEN=$(curl -k -X POST $BASE_URL/token  -H 'Content-Type: application/x-www-form-urlencoded' -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${KEYCLOAK_CLIENT_SECRET}" | jq -r .access_token)
```

Run below command to get response from API
```
curl -k ${BASE_URL}/Meta-Llama-3.1-70B-Instruct/v1/completions -X POST -d '{"model": "meta-llama/Llama-3.1-70B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}' -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"

```