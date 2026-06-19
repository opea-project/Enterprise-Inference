# Ingress & Routing Architecture

This document explains how traffic is routed to vLLM models in Enterprise Inference (EI),
covering both the automated EI deployment path and direct `helm install` deployment.

---

## Table of Contents
- [Components Overview](#components-overview)
- [EI Deployment Architecture](#ei-deployment-architecture)
- [Direct Helm Deployment Architecture](#direct-helm-deployment-architecture)
- [Side-by-Side Comparison](#side-by-side-comparison)
- [The Dual Ingress Template Issue](#the-dual-ingress-template-issue)
- [Helm Resources Created Per Model](#helm-resources-created-per-model)

---

## Components Overview

| Component | Role |
|-----------|------|
| **nginx Ingress Controller** | Terminates TLS, routes external traffic by hostname/path |
| **APISIX Gateway** (`auth-apisix-gateway`) | API gateway — enforces OIDC auth, rewrites paths |
| **APISIX Ingress Controller** | Watches `ApisixRoute` objects and programs APISIX |
| **ApisixRoute** | Per-model routing rule: maps URL path → vLLM service |
| **K8s Ingress** (`ingress.yaml`) | Routes nginx → APISIX gateway for a specific model path |
| **vLLM Service** | ClusterIP service exposing the vLLM pod |

---

## EI Deployment Architecture

When deploying through EI (`inference_stack_deploy.sh`) with `deploy_keycloak_apisix=on`:

```
┌─────────────────────────────────────────────────────────────────────┐
│  External Client                                                     │
│  curl https://api.example.com/TinyLlama-1.1B-Chat-v1.0-vllmcpu/... │
└───────────────────────┬─────────────────────────────────────────────┘
                        │ HTTPS (port 443)
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  nginx Ingress Controller                                            │
│  Matches: host=api.example.com                                      │
│           path=/TinyLlama-1.1B-Chat-v1.0-vllmcpu/(.*)              │
│  Routes to: auth-apisix-gateway:80                                  │
│  (Ingress in auth-apisix namespace, class: nginx)                   │
└───────────────────────┬─────────────────────────────────────────────┘
                        │ HTTP (port 80)
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  APISIX Gateway  (auth-apisix-gateway)                              │
│  - Validates Bearer token via Keycloak OIDC introspection           │
│  - Rewrites path: /TinyLlama-1.1B-Chat-v1.0-vllmcpu/v1/... → /v1/ │
└───────────────────────┬─────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ApisixRoute  (per-model)                                           │
│  name: tinyllama-1-1b-cpu-vllm-apisixroute                         │
│  namespace: default                                                  │
│  Plugins: openid-connect, proxy-rewrite                             │
└───────────────────────┬─────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  vLLM Service  (ClusterIP)                                          │
│  tinyllama-1-1b-cpu-vllm-service:80                                 │
└───────────────────────┬─────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  vLLM Pod                                                           │
│  Model: TinyLlama/TinyLlama-1.1B-Chat-v1.0                        │
└─────────────────────────────────────────────────────────────────────┘
```

### What EI Does Before Running helm install

EI's Ansible playbook (`deploy-inference-models.yml`) handles the dual ingress template
problem at the filesystem level **before** running `helm install`:

**On vanilla Kubernetes (Xeon / non-EKS):**
```
Ansible: "Remove EKS ingress template for VLLM when not on EKS"
  → deletes core/helm-charts/vllm/templates/ingress_eks.yaml from remote machine
  → helm install only renders ingress.yaml (class: nginx) ✓
```

**On EKS:**
```
Ansible: "Use EKS-specific ingress configuration for VLLM"
  → copies ingress_eks.yaml → ingress.yaml  (replaces it)
  → deletes ingress_eks.yaml
  → helm install only renders the ALB ingress ✓
```

**On OpenShift:**
```
Ansible: Removes both ingress.yaml and ingress_eks.yaml
  → deploys an OpenShift Route instead (route.enabled=true)
```

### EI helm install (simplified, vanilla Kubernetes)

```bash
helm install <model> ./vllm \
  --values xeon-values.yaml \
  --set ingress.enabled=true \
  --set ingress.host=api.example.com \
  --set ingress.secretname=api.example.com \
  --set apisix.enabled=true \
  --set platform=vanilla \
  --set oidc.client_id=<id> \
  --set oidc.client_secret=<secret>
```

> `ingress.enabled=true` is set only when `deploy_keycloak_apisix=on` in `inference-config.cfg`.

---

## Direct Helm Deployment Architecture

When running `helm install` directly **without** EI on vanilla Kubernetes:

### The Problem — Both ingress templates render

The vLLM chart has two ingress templates that both trigger when `ingress.enabled=true`:

| Template | Condition | Class |
|----------|-----------|-------|
| `ingress.yaml` | `{{- if .Values.ingress.enabled }}` | `nginx` |
| `ingress_eks.yaml` | `{{- if .Values.ingress.enabled }}` | `alb` |

Both create an Ingress with the **same name** in the **same namespace**.
`ingress_eks.yaml` renders last and overwrites `ingress.yaml` → ALB ingress wins.

```
helm install with ingress.enabled=true (no fix):

  ingress.yaml      → tinyllama-1-1b-cpu-vllm-ingress (class: nginx)  ← created first
  ingress_eks.yaml  → tinyllama-1-1b-cpu-vllm-ingress (class: alb)    ← overwrites
                                                                  ↑
                                            Result: ALB ingress — broken on vanilla k8s
```

### The Fix — Platform guard on ingress_eks.yaml

Change the condition in `core/helm-charts/vllm/templates/ingress_eks.yaml` from:

```yaml
{{- if .Values.ingress.enabled }}
```

to:

```yaml
{{- if and .Values.ingress.enabled (eq .Values.platform "eks") }}
```

With `platform: vanilla` (default in `values.yaml`), `ingress_eks.yaml` never renders
on non-EKS clusters. Only `ingress.yaml` (nginx) renders → correct result.

```
helm install with ingress.enabled=true (after fix):

  ingress.yaml      → tinyllama-1-1b-cpu-vllm-ingress (class: nginx)  ✓
  ingress_eks.yaml  → skipped  (platform=vanilla)                      ✓
```

### Correct direct helm command

```bash
helm install tinyllama-1-1b-cpu ./core/helm-charts/vllm \
  --values ./core/helm-charts/vllm/xeon-values.yaml \
  --set LLM_MODEL_ID="TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  --set global.HUGGINGFACEHUB_API_TOKEN="$HUGGING_FACE_HUB_TOKEN" \
  --set ingress.enabled=true \
  --set ingress.host="${BASE_URL}" \
  --set ingress.secretname="${BASE_URL}" \
  --set oidc.client_id="$KEYCLOAK_CLIENT_ID" \
  --set oidc.client_secret="$KEYCLOAK_CLIENT_SECRET" \
  --set apisix.enabled=true \
  --set tensor_parallel_size="1" \
  --set pipeline_parallel_size="1"
```

> **Note:** `ingress.host` must always be set even if `ingress.enabled=false`, because
> the `ApisixRoute` template uses it as the hostname:
> `{{ .Values.route.host | default .Values.ingress.host }}`

---

## Side-by-Side Comparison

| | EI Deployment | Direct Helm (after fix) |
|--|---------------|------------------------|
| **ingress.enabled** | `true` when `deploy_keycloak_apisix=on` | Set explicitly by user |
| **ingress_eks.yaml** | Deleted by Ansible before helm runs | Skipped by platform guard |
| **Ingress class** | `nginx` ✓ | `nginx` ✓ |
| **ApisixRoute created** | Yes (`apisix.enabled=true`) | Yes (`apisix.enabled=true`) |
| **Traffic path** | nginx → APISIX → vLLM | nginx → APISIX → vLLM |
| **OIDC auth** | Enforced by APISIX (openid-connect plugin) | Enforced by APISIX (openid-connect plugin) |
| **Why no ingress without fix** | Works (Ansible deletes EKS template) | ALB ingress created instead of nginx |

---

## Helm Resources Created Per Model

When `helm install` runs with `apisix.enabled=true` and `ingress.enabled=true`:

| Resource | Kind | Namespace | Purpose |
|----------|------|-----------|---------|
| `<model>-vllm-ingress` | Ingress (nginx) | `auth-apisix` | Routes nginx → APISIX gateway |
| `<model>-vllm-apisixroute` | ApisixRoute | `default` | Routes APISIX → vLLM service |
| `<model>-vllm-service` | Service (ClusterIP) | `default` | Exposes vLLM pod |
| `<model>-vllm-secret` | Secret | `default` | OIDC client credentials for APISIX |
| `<model>-vllm-configmap` | ConfigMap | `default` | vLLM environment variables |
| `<model>-vllm` | Deployment | `default` | vLLM pod |
| `<model>-vllm-pvc` | PersistentVolumeClaim | `default` | Model weights storage |
