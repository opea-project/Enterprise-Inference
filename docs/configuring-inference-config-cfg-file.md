An example and Explaination of the `inference-config.cfg` file:
`````
cluster_url=example.com
cert_file=/path/to/cert/file.pem
key_file=/path/to/key/file.pem
keycloak_client_id=my-client-id
keycloak_admin_user=your-keycloak-admin-user
keycloak_admin_password=changeme
hugging_face_token=your_hugging_face_token
models=
cpu_or_gpu=
deploy_kubernetes_fresh=on
deploy_ingress_controller=on
deploy_keycloak_apisix=on
deploy_genai_gateway=on
deploy_observability=on
deploy_llm_models=on

`````
Make sure to update the values in the inference-config.cfg file according to your requirements before running the Intel AI for Enterprise Inference.


>
> - If `deploy_kubernetes_fresh` is set to `on`, a fresh Kubernetes cluster will be initialized as per the deployment configuration.
> - If `deploy_ingress_controller` is set to `on`, ingress controller will be configured to route external traffic to the cluster
> - If `deploy_keycloak_apisix` is set to `on`, Keycloak and APISIX will be deployed for Model API Authentication
> - If `deploy_genai_gateway` is set to `on`, the GenAI Gateway will be deployed.
> - If `deploy_genai_gateway` is set to `on`, you must choose only one authentication method: either enable Keycloak and APISIX (`deploy_keycloak_apisix=on`) for external authentication, or use the GenAI Gateway's built-in authentication by setting `deploy_keycloak_apisix=off`. Please not enable both authentication methods at the same time.
> - If `deploy_observability` is set to `on`, the observability stack will be deployed for monitoring.
> - If `deploy_llm_models` is set to `on`, the selected models will be deployed for inferencing
> - The `cert_file` and `key_file` paths should be set according to the instructions for generating certificates for development and production environments, as documented.
> - The `models` value corresponds to the pre-validated LLM models listed in the documentation.

> - The `keycloak_client_id` is the client ID used for accessing APIs through Keycloak.
> - The `keycloak_admin_user` is the administrator username for Keycloak.
> - The `keycloak_admin_password` is the administrator password for Keycloak.
> - If `deploy_keycloak_apisix` is set to `off`, the `keycloak_client_id`, `keycloak_admin_user`, and `keycloak_admin_password` values will have no effect.
> - The `hugging_face_token` is the token used for pulling LLM models from Hugging Face. 
> - If `deploy_llm_models` is set to `off`, the `hugging_face_token` value will be ignored.
> - The `cpu_or_gpu` value specifies whether to deploy models for CPU or Intel Gaudi.
>

For running behind corporate proxy, please refer to this [guide](./running-behind-proxy.md)
