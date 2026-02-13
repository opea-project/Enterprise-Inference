# Agentic AI Plugin - Quick Start Guide

## Overview

The **Agentic AI Plugin** provides a visual platform for building AI agents, multi-agent systems, and intelligent workflows. The current implementation uses **Flowise**, an open-source drag-and-drop tool for creating conversational AI, RAG applications, and workflow automation without coding.

**About Flowise:** [Official Documentation](https://docs.flowiseai.com/) | [GitHub](https://github.com/FlowiseAI/Flowise)

**Key Features:**
- Visual workflow builder with drag-and-drop interface
- Pre-built agent templates and marketplace
- Multi-agent collaboration support
- Integration with deployed LLM models
- RAG (Retrieval Augmented Generation) support
- API integration for external services

---

## Deployment

### Prerequisites
- Intel® AI for Enterprise Inference automation deployed
- Kubernetes cluster with ingress controller
- TLS certificate with Flowise subdomain in SANs (flowise-<your-domain>)

### Step 1: Enable Plugin

Edit the main configuration:
```bash
vim core/inventory/inference-config.cfg
```

Set:
```properties
deploy_agenticai_plugin=on
```

### Step 2: Deploy

```bash
cd core
bash inference-stack-deploy.sh
```

Select: `1) Provision Enterprise Inference Cluster`

### Step 3: Verify

```bash
kubectl get pods -n flowise
```

Expected output:
```
NAME                                 READY   STATUS    RESTARTS   AGE
flowise-xxxxx                        1/1     Running   0          5m
flowise-postgresql-0                 1/1     Running   0          5m
flowise-redis-master-0               1/1     Running   0          5m
flowise-worker-xxxxx                 1/1     Running   0          5m
```

---

## Initial Setup

### Accessing the Platform

Open in browser:
```
https://flowise-<your-domain>
```

> **Note:** The subdomain is "flowise" as this is the current implementation. Future versions may support custom subdomains.

### First Time Setup (Account Creation)

When you first access the platform, you'll see the **Setup Account** page:

1. **Administrator Name:** Your display name (e.g., "John Doe")
2. **Administrator Email:** Valid email address - **this becomes your login ID**
3. **Password:** Must contain:
   - At least 8 characters
   - One lowercase letter
   - One uppercase letter
   - One digit
   - One special character
4. **Confirm Password:** Re-enter password
5. Click **"Sign Up"**

> **Important:** Account setup is local to your server. No external connections are made. Your data stays on your infrastructure.

### Subsequent Logins

After account creation, use:
- **Email:** The email you registered
- **Password:** Your chosen password

---

## Using the Platform

### Add a Credential

Flowise stores API keys and credentials that can be reused by workflow nodes. Credentials are encrypted in the database.

1. In the left sidebar, click **Credentials**
2. Click **Add Credential**
3. Choose **OpenAI API**
4. Provide:
   - **Credential Name**: e.g., `InternalLLM`
   - **API Key**: you can enter `sk-dummy` (for internal models)
5. Click **Save**

⚠️ This UI uses OpenAI API credential type because Flowise nodes expect this format; for internal models there may not be a real API key.

### Connecting to Deployed Models

The Agentic AI Plugin is designed to work seamlessly with models deployed on the same Kubernetes cluster, avoiding external network calls for better performance and security.

#### Using Locally Deployed Models

**For models deployed on the same cluster:**

Since your LLM models are deployed within the same Kubernetes cluster as Flowise, use internal service endpoints for optimal performance:

1. Add **"Custom Chat Model"** or **"OpenAI Compatible"** node to your workflow
2. Configure with Kubernetes internal service endpoint:
   - **Base URL/Endpoint:** `http://<service-name>.<namespace>.svc.cluster.local:<port>/v1`
     - Example: `http://llama-2-7b-service.default.svc.cluster.local:8000/v1`
   - **Model Name/ID:** Your model identifier
     - Example: `meta-llama/Llama-2-7b-chat-hf`
   - **API Key:** `sk-dummy` (use APIKey from keycloak or GenAI gateway)

**Find your deployed model services:**
```bash
kubectl get svc | grep -E "vllm"
```

**Benefits of using internal endpoints:**
- ✅ **Faster:** No network egress/ingress - direct cluster networking
- ✅ **Secure:** Traffic stays within the cluster
- ✅ **No External Costs:** No internet bandwidth charges
- ✅ **Lower Latency:** Milliseconds vs. seconds

#### Using External/Cloud Models (Optional)

**For models hosted externally or in the cloud:**

If you need to use OpenAI, Anthropic, or other external models:

1. Add the appropriate chat model node (e.g., "ChatOpenAI", "ChatAnthropic")
2. Configure:
   - **Endpoint:** Cloud provider endpoint (e.g., `https://api.openai.com/v1`)
   - **Model ID:** Cloud model name (e.g., `gpt-4`, `claude-3-opus`)
   - **API Key:** Your cloud provider API key

#### Template Configuration

The included `software-team.json` template uses placeholder values that you should replace:
- **`your-model-endpoint`** → Replace with actual service endpoint
- **`your-model-id`** → Replace with actual model name/ID

After importing the template, update all LLM nodes with your model configuration.


### How to Load an sample AgentFlow Template

1. From the **left sidebar**, click **AgentFlows**
2. Click **Add New**
3. An empty Agent editor will open  
   (You will see a blank canvas with the title “Untitled Agent”)
4. In the **top-right corner**, Click **Settings** gear icon and select **Load Agents**
5. Select the provided agent template `.json` file.
   Pre-built agentflow template available at:
   ```
   plugins/agenticai/templates/software-team.json
   ```
6. The agent configuration will load automatically
7. In all the LLM Nodes choose the credentials that is created in above step. And also update model and basepath.
8. Click the **Save (💾) icon**
9. Enter a name for the agent and save


---

## Administration

### Common Commands

**View Logs:**
```bash
kubectl logs -n flowise -l app.kubernetes.io/name=flowise -f
kubectl logs -n flowise -l app=flowise-worker -f
```

**Check Status:**
```bash
kubectl get pods,svc,ingress -n flowise
```

**Database Backup:**
```bash
kubectl exec -n flowise flowise-postgresql-0 -- pg_dump -U flowise flowise > flowise-backup.sql
```

**Restart Platform:**
```bash
kubectl rollout restart deployment/flowise -n flowise
```

**Scale Workers:**
```bash
kubectl scale deployment flowise-worker -n flowise --replicas=5
```

### Database Passwords

Backend passwords (PostgreSQL, Redis) are auto-generated during deployment and stored in:
```
core/kubespray/config/vault.yml
```

Variables:
- `agenticai_postgres_password`
- `agenticai_redis_password`

> **Note:** User login passwords are set by users themselves during account creation, not from vault.

---

## Troubleshooting

### Cannot Access UI

**Check ingress:**
```bash
kubectl get ingress -n flowise
kubectl describe ingress flowise -n flowise
```

**Verify certificate includes subdomain:**
```bash
openssl s_client -connect flowise-<your-domain>:443 -servername flowise-<your-domain> < /dev/null | openssl x509 -noout -text | grep DNS
```

### Pods Not Starting

```bash
kubectl describe pod -n flowise <pod-name>
kubectl logs -n flowise <pod-name> --previous
```

### Database Connection Issues

```bash
# Test connectivity from Flowise pod
kubectl exec -n flowise <flowise-pod> -- nc -zv flowise-postgresql 5432

# Check PostgreSQL logs
kubectl logs -n flowise flowise-postgresql-0
```

---

## Additional Resources

- Official Documentation: https://docs.flowiseai.com/
- GitHub Repository: https://github.com/FlowiseAI/Flowise
- Community Discord: https://discord.gg/jbaHfsRVBW
- Example Workflows: https://docs.flowiseai.com/use-cases

---
