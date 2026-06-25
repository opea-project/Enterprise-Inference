# Ingress to Envoy Gateway Migration Guide

> **Enterprise Inference — Edge Traffic Migration**
> NGINX Ingress Controller (`networking.k8s.io/v1 Ingress`) → Envoy Gateway (`gateway.networking.k8s.io/v1 HTTPRoute`)

---

## Table of Contents

1. [Why This Migration](#why-this-migration)
2. [Architecture — Before (NGINX Ingress)](#architecture--before-nginx-ingress)
3. [Architecture — After (Envoy Gateway)](#architecture--after-envoy-gateway)
4. [Concept Mapping](#concept-mapping)
5. [What Changed](#what-changed)
6. [What Did NOT Change](#what-did-not-change)
7. [File-by-File Change Inventory](#file-by-file-change-inventory)
8. [Deployment Workflow](#deployment-workflow)
9. [Configuration](#configuration)
10. [Route Mapping Reference](#route-mapping-reference)
11. [Platform Matrix](#platform-matrix)
12. [Rollback Procedure](#rollback-procedure)

---

## Why This Migration

Kubernetes `networking.k8s.io/v1 Ingress` is approaching End-of-Life. The Kubernetes community has standardized on the **Gateway API** (`gateway.networking.k8s.io/v1`) as the successor, offering:

| Aspect | Ingress (Old) | Gateway API (New) |
|--------|---------------|-------------------|
| API maturity | Feature-frozen, EOL path | GA since K8s 1.26, actively developed |
| Routing | Single host/path rules, vendor annotations | Rich match types (headers, methods, query params) |
| TLS | Per-Ingress resource | Centralized at Gateway listener |
| Multi-tenancy | Flat, single namespace | Role-based: Infra → GatewayClass, Cluster → Gateway, App → HTTPRoute |
| URL rewriting | Vendor-specific annotation (`nginx.ingress.kubernetes.io/rewrite-target`) | Standard `URLRewrite` filter |
| Vendor lock-in | NGINX-specific annotations | Portable across Envoy, Istio, Traefik, etc. |

---

## Architecture — Before (NGINX Ingress)

```
┌───────────┐
│  Client    │
│ (HTTPS)    │
└─────┬─────┘
      │ :443
      ▼
┌─────────────────────────────────────────────────┐
│  NGINX Ingress Controller                       │
│  namespace: ingress-nginx                       │
│  Helm chart: ingress-nginx/ingress-nginx v4.12.2│
│  hostPort: 80, 443                              │
│  Tolerations: control-plane                     │
│  Affinity: ei-infra-eligible nodes              │
└────┬────┬────┬────┬────┬────┬────┬──────────────┘
     │    │    │    │    │    │    │
     ▼    ▼    ▼    ▼    ▼    ▼    ▼
  ┌──────────────────────────────────────────┐
  │  networking.k8s.io/v1 Ingress resources  │
  │  ingressClassName: nginx                 │
  │  nginx.ingress.kubernetes.io/* annotations│
  ├──────────────────────────────────────────┤
  │ • model-ingress      → vLLM/TGI/TEI svc │
  │ • genai-gw-ingress   → LiteLLM :4000    │
  │ • keycloak-ingress   → Keycloak/APISIX  │
  │ • dashboard-ingress  → K8s Dashboard    │
  │ • grafana-ingress    → Grafana :80       │
  │ • flowise-root       → Flowise :3000     │
  │ • mcp-server         → MCP Server        │
  └──────────────────────────────────────────┘
```

### Key Characteristics (Before)

- **Controller:** NGINX Ingress Controller deployed via Helm (`ingress-nginx` chart v4.12.2)
- **Namespace:** `ingress-nginx`
- **TLS:** Each Ingress resource carried its own `tls:` block with `secretName`
- **Rewriting:** `nginx.ingress.kubernetes.io/rewrite-target: /$1` annotation with regex capture groups
- **Pod placement:** `hostPort: 80/443` with control-plane tolerations and `ei-infra-eligible` node affinity
- **EKS variant:** Separate `ingress_eks.yaml` templates with `ingressClassName: alb` and ALB annotations

---

## Architecture — After (Envoy Gateway)

```
┌───────────┐
│  Client    │
│ (HTTPS)    │
└─────┬─────┘
      │ :443
      ▼
┌─────────────────────────────────────────────────┐
│  Envoy Gateway                                   │
│  namespace: envoy-gateway-system                 │
│                                                   │
│  ┌─────────────────────────────────────────┐     │
│  │ GatewayClass: envoy                     │     │
│  │ controller: gateway.envoyproxy.io       │     │
│  │ parametersRef → EnvoyProxy              │     │
│  └─────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────┐     │
│  │ EnvoyProxy: enterprise-proxy-config     │     │
│  │ hostNetwork: true                       │     │
│  │ Tolerations: control-plane              │     │
│  │ Affinity: ei-infra-eligible nodes       │     │
│  │ podAntiAffinity: spread across hosts    │     │
│  └─────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────┐     │
│  │ Gateway: enterprise-edge-gateway        │     │
│  │ Listeners:                              │     │
│  │   - https :443 (TLS Terminate)          │     │
│  │   - http  :80                           │     │
│  │ allowedRoutes: All namespaces           │     │
│  │ TLS cert: <cluster_url> secret          │     │
│  └─────────────────────────────────────────┘     │
└────┬────┬────┬────┬────┬────┬────┬───────────────┘
     │    │    │    │    │    │    │
     ▼    ▼    ▼    ▼    ▼    ▼    ▼
  ┌──────────────────────────────────────────┐
  │  gateway.networking.k8s.io/v1 HTTPRoutes │
  │  parentRefs: enterprise-edge-gateway     │
  │  Standard filters (URLRewrite, etc.)     │
  ├──────────────────────────────────────────┤
  │ • model-httproute    → vLLM/TGI/TEI svc │
  │ • genai-gw-httproute → LiteLLM :4000    │
  │ • keycloak-httproute → Keycloak/APISIX  │
  │ • dashboard-httproute→ K8s Dashboard     │
  │ • grafana-httproute  → Grafana :80       │
  │ • flowise-root       → Flowise :3000     │
  │ • mcp-httproute      → MCP Server        │
  └──────────────────────────────────────────┘
```

### Key Characteristics (After)

- **Controller:** Envoy Gateway deployed via OCI Helm chart (`gateway-helm v1.2.0`)
- **Namespace:** `envoy-gateway-system`
- **TLS:** Centralized at the Gateway listener — HTTPRoutes do NOT carry TLS config
- **Rewriting:** Standard Gateway API `URLRewrite` filter with `ReplacePrefixMatch`
- **Pod placement:** `hostNetwork: true` with same tolerations and node affinity as before
- **EKS variant:** ALB `ingress_eks.yaml` templates kept as-is (separate migration path)

---

## Concept Mapping

| NGINX Ingress Concept | Envoy Gateway Equivalent | Notes |
|----------------------|--------------------------|-------|
| `ingress-nginx` Helm chart | `gateway-helm` OCI chart | Deployed to `envoy-gateway-system` |
| `IngressClass: nginx` | `GatewayClass: envoy` | References `EnvoyProxy` for pod config |
| — | `EnvoyProxy` CR | New: configures proxy pod placement, replicas, hostNetwork |
| — | `Gateway` CR | New: defines listeners (HTTPS/HTTP), TLS termination |
| `Ingress` resource | `HTTPRoute` resource | 1:1 replacement per service |
| `ingressClassName: nginx` | `parentRefs: [{name: enterprise-edge-gateway}]` | Routes reference the Gateway, not a class |
| `tls:` block on each Ingress | TLS on Gateway listener only | Eliminates per-route TLS duplication |
| `nginx.ingress.kubernetes.io/rewrite-target: /$1` | `filters: [{type: URLRewrite, urlRewrite: {path: {type: ReplacePrefixMatch}}}]` | Standard API, no vendor annotation |
| `nginx.ingress.kubernetes.io/backend-protocol: HTTPS` | (handled at Backend/service level) | — |
| `hostPort: 80, 443` | `hostNetwork: true` on EnvoyProxy | Equivalent node-level port binding |
| `pathType: ImplementationSpecific` + regex | `path.type: PathPrefix` | Gateway API uses structured prefix matching |

---

## What Changed

### Files Modified (20 files)

| # | Category | File | Summary |
|---|----------|------|---------|
| 1 | **Controller Playbook** | `core/playbooks/deploy-ingress-controller.yml` | Entire file: NGINX Helm → Envoy Gateway + GatewayClass + EnvoyProxy + Gateway |
| 2 | **Shell Script** | `core/lib/components/ingress-controller.sh` | Updated message and `--extra-vars` |
| 3 | **Shell Script** | `core/lib/cluster/deployment/fresh-install.sh` | Updated log messages |
| 4 | **Shell Script** | `core/lib/user-menu/parse-user-prompts.sh` | Updated interactive prompt text |
| 5 | **Metadata** | `core/inventory/metadata/inference-metadata.cfg` | `ingress_controller=4.12.2` → `envoy_gateway_version=v1.2.0` |
| 6 | **Helm Template** | `core/helm-charts/vllm/templates/ingress.yaml` | `Ingress` → `HTTPRoute` with `URLRewrite` filter |
| 7 | **Helm Template** | `core/helm-charts/tgi/templates/ingress.yaml` | `Ingress` → `HTTPRoute` with `URLRewrite` filter |
| 8 | **Helm Template** | `core/helm-charts/tei/templates/ingress.yaml` | `Ingress` → `HTTPRoute` with `URLRewrite` filter |
| 9 | **Helm Template** | `core/helm-charts/teirerank/templates/ingress.yaml` | `Ingress` → `HTTPRoute` with `URLRewrite` filter |
| 10 | **Helm Template** | `core/helm-charts/ovms/templates/ingress.yaml` | `Ingress` → `HTTPRoute` with `URLRewrite` filter |
| 11 | **Helm Template** | `core/helm-charts/genai-gateway/templates/ingress.yaml` | `Ingress` → `HTTPRoute` |
| 12 | **Helm Template** | `core/helm-charts/keycloak/templates/ingress.yaml` | `Ingress` → `HTTPRoute` |
| 13 | **Helm Template** | `core/helm-charts/mcp-server-template/templates/ingress.yaml` | `Ingress` → `HTTPRoute` |
| 14 | **Playbook** | `core/playbooks/deploy-cluster-config.yml` | Dashboard Ingress → HTTPRoute |
| 15 | **Playbook** | `core/playbooks/deploy-observability.yml` | Grafana Ingress (non-EKS) → HTTPRoute |
| 16 | **Playbook** | `core/playbooks/deploy-genai-gateway.yml` | Langfuse: disabled built-in Ingress, added HTTPRoute |
| 17 | **Playbook** | `core/playbooks/deploy-keycloak-tls-cert.yml` | Keycloak Ingress disabled for non-EKS, added HTTPRoute |
| 18 | **Playbook** | `core/playbooks/deploy-keycloak-controller.yml` & `deploy-keycloak-service.yml` | Helm repo refs: ingress-nginx → envoy-gateway |
| 19 | **Istio** | `core/playbooks/deploy-istio.yml` & `deploy-istio-openshift.yml` | Namespace `ingress-nginx` → `envoy-gateway-system` |
| 20 | **Istio** | `core/helm-charts/istio/peer-auth-ingress.yaml` | PeerAuth target: `ingress-nginx` → `envoy-gateway-system` pods |
| 21 | **Plugin** | `plugins/agenticai/playbooks/deploy-agenticai-plugin.yml` | Flowise Ingress → HTTPRoute |

---

## What Did NOT Change

| Item | Reason |
|------|--------|
| **`values.yaml`** in all Helm charts | Keys `ingress.enabled`, `ingress.host`, `ingress.secretname` kept identical |
| **`inference-config.cfg`** | `deploy_ingress_controller=on` still controls edge gateway deployment |
| **Template filenames** | All `ingress.yaml` filenames kept (only content changed to HTTPRoute) |
| **Shell function name** | Renamed to `run_edge_gateway_playbook()` (previously `run_ingress_nginx_playbook()`) |
| **EKS ALB templates** | `ingress_eks.yaml` variants with `ingressClassName: alb` are untouched |
| **OpenShift Routes** | `route.yaml` templates are not Ingress — unaffected |
| **APISIX integration** | APISIX catch-all routing through HTTPRoutes works the same way |
| **Model deployment logic** | `install-model.sh`, `deploy-inference-models.yml` — no changes to `ingress_enabled` logic |
| **Brownfield detection** | `setup-bastion.yml` pre-flight checks kept (informational only) |

---

## Deployment Workflow

The deployment sequence is **unchanged**. The `deploy_ingress_controller=on` flag in `inference-config.cfg` triggers the edge gateway step:

```
inference-stack-deploy.sh
  └── fresh-install.sh
        ├── 1. Kubernetes cluster setup        (if deploy_kubernetes_fresh=on)
        ├── 2. Cluster config (dashboard)       ← HTTPRoute for dashboard
        ├── 3. NRI CPU Balloons                 (if cpu deployment)
        ├── 4. Habana AI Operator               (if GPU)
        ├── 5. Ceph storage                     (if deploy_ceph=on)
        │
        ├── 6. Edge Gateway Controller          (if deploy_ingress_controller=on)
        │       └── deploy-ingress-controller.yml
        │             ├── Install Gateway API CRDs (v1.2.0)
        │             ├── Deploy Envoy Gateway Helm chart
        │             ├── Create EnvoyProxy (pod placement config)
        │             ├── Create GatewayClass: envoy
        │             ├── Create TLS Secret in envoy-gateway-system
        │             └── Create Gateway: enterprise-edge-gateway
        │
        ├── 7. Keycloak + APISIX                (if deploy_keycloak_apisix=on)
        │       └── HTTPRoute for Keycloak created here
        ├── 8. GenAI Gateway (LiteLLM)          (if deploy_genai_gateway=on)
        │       └── HTTPRoute for LiteLLM + Langfuse trace
        ├── 9. Observability (Grafana)          (if deploy_observability=on)
        │       └── HTTPRoute for Grafana
        ├── 10. Agentic AI Plugin               (if deploy_agenticai_plugin=on)
        │       └── HTTPRoute for Flowise
        ├── 11. Istio                           (if deploy_istio=on)
        │       └── Labels envoy-gateway-system for ambient mode
        └── 12. LLM Model Deployment            (if deploy_llm_models=on)
                └── HTTPRoutes created per model via Helm templates
```

---

## Configuration

### No inference-config.cfg Changes Required

The existing config toggle works the same way:

```ini
# Controls edge gateway deployment (formerly NGINX, now Envoy Gateway)
deploy_ingress_controller=on
```

### Metadata Version

In `core/inventory/metadata/inference-metadata.cfg`:

```ini
# Before:
# ingress_controller="4.12.2"

# After:
envoy_gateway_version="v1.2.0"
```

### Helm Chart values.yaml — No Changes

All `values.yaml` files retain the same `ingress:` block:

```yaml
ingress:
  enabled: false    # Set to true to enable the HTTPRoute resource
  host: ""
  namespace: default
  secretname: ""    # (used by EKS ALB variant only)
```

---

## Route Mapping Reference

### Model Serving (vLLM, TGI, TEI, TEI-Rerank, OVMS)

| Before (Ingress) | After (HTTPRoute) |
|-------------------|-------------------|
| `ingressClassName: nginx` | `parentRefs: [{name: enterprise-edge-gateway, namespace: envoy-gateway-system}]` |
| `nginx.ingress.kubernetes.io/rewrite-target: /$1` | `filters: [{type: URLRewrite, urlRewrite: {path: {type: ReplacePrefixMatch, replacePrefixMatch: /}}}]` |
| `path: /model-name/(.*)` | `path: {type: PathPrefix, value: /model-name}` |
| `pathType: ImplementationSpecific` | (PathPrefix is the type) |
| `tls: [{hosts: [host], secretName: secret}]` | (TLS handled at Gateway level) |

**Example — vLLM HTTPRoute:**

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: vllm-model-httproute
spec:
  parentRefs:
    - name: enterprise-edge-gateway
      namespace: envoy-gateway-system
  hostnames:
    - api.example.com
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /Meta-Llama-3.1-8B-Instruct
      filters:
        - type: URLRewrite
          urlRewrite:
            path:
              type: ReplacePrefixMatch
              replacePrefixMatch: /
      backendRefs:
        - name: vllm-model-service
          port: 80
```

### Infrastructure Services

| Service | Path | Type | Notes |
|---------|------|------|-------|
| GenAI Gateway (LiteLLM) | `/` | PathPrefix | Full catch-all for LiteLLM API |
| Keycloak (via APISIX) | `/token` | Exact | Token endpoint only |
| Kubernetes Dashboard | `/dashboard` | PathPrefix | URLRewrite strips prefix |
| Grafana | `/observability` | PathPrefix | `serve_from_sub_path: true` in Grafana |
| Flowise | `/` (subdomain) | PathPrefix | Hostname: `flowise-<cluster_url>` |
| MCP Server | `/health`, `/sse` | PathPrefix | SSE-optimized (no special annotation needed) |
| Langfuse Trace | `/` (subdomain) | PathPrefix | Hostname: `trace-<cluster_url>` |

---

## Platform Matrix

| Platform | Edge Gateway | Model Routes | Infra Routes | Auth Mode |
|----------|-------------|-------------|-------------|-----------|
| **Vanilla K8s** | Envoy Gateway (HTTPRoutes) | HTTPRoute | HTTPRoute | Keycloak or LiteLLM |
| **EKS** | AWS ALB (Ingress with `ingressClassName: alb`) | ALB Ingress | ALB Ingress | Same |
| **OpenShift** | OpenShift Routes (`route.yaml`) | Route | Route | Same |

> **Note:** EKS ALB and OpenShift Routes are **not affected** by this migration. Only vanilla Kubernetes deployments use the new Envoy Gateway path.

---

## Key Resources Created by deploy-ingress-controller.yml

```yaml
# 1. Gateway API CRDs (from upstream)
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/standard-install.yaml

# 2. Envoy Gateway Controller (Helm)
helm upgrade --install eg oci://docker.io/envoyproxy/gateway-helm
  --version v1.2.0
  --namespace envoy-gateway-system

# 3. EnvoyProxy — proxy pod configuration
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: EnvoyProxy
metadata:
  name: enterprise-proxy-config
  namespace: envoy-gateway-system
spec:
  provider:
    type: Kubernetes
    kubernetes:
      envoyDeployment:
        replicas: <ei-infra-eligible node count>
        pod:
          tolerations: [control-plane, master]
          affinity: {ei-infra-eligible nodes, pod anti-affinity}
        patch:
          spec:
            template:
              spec:
                hostNetwork: true         # Binds ports 80/443 to node
                dnsPolicy: ClusterFirstWithHostNet
      envoyService:
        type: ClusterIP

# 4. GatewayClass
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: envoy
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
  parametersRef: {EnvoyProxy: enterprise-proxy-config}

# 5. Gateway
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: enterprise-edge-gateway
  namespace: envoy-gateway-system
spec:
  gatewayClassName: envoy
  listeners:
    - name: https
      protocol: HTTPS
      port: 443
      tls:
        mode: Terminate
        certificateRefs: [{name: <cluster_url>}]
    - name: http
      protocol: HTTP
      port: 80
  allowedRoutes:
    namespaces: {from: All}
```

---

## Rollback Procedure

If a rollback to NGINX Ingress is needed:

1. **Revert the code** — `git checkout` the prior commit on the 20 modified files
2. **Remove Envoy Gateway resources:**
   ```bash
   kubectl delete gateway enterprise-edge-gateway -n envoy-gateway-system
   kubectl delete gatewayclass envoy
   kubectl delete envoyproxy enterprise-proxy-config -n envoy-gateway-system
   helm uninstall eg -n envoy-gateway-system
   kubectl delete namespace envoy-gateway-system
   ```
3. **Re-deploy** — run `inference-stack-deploy.sh` which will install NGINX Ingress Controller and create Ingress resources

---

## FAQ

**Q: Do I need to change `inference-config.cfg`?**
A: No. `deploy_ingress_controller=on` works exactly as before.

**Q: Will my existing model deployments break?**
A: If upgrading in-place, you need to run the edge gateway deployment step first, then re-deploy models so HTTPRoutes replace the old Ingress resources.

**Q: What about EKS deployments?**
A: EKS uses the AWS ALB Ingress Controller (`ingressClassName: alb`). This migration does not affect EKS deployments.

**Q: What about the APISIX integration?**
A: APISIX still works the same way. When `apisix.enabled=true`, the HTTPRoute backend points to `auth-apisix-gateway:80` instead of the model service directly — identical behavior to the old Ingress.

**Q: Where is TLS configured now?**
A: TLS terminates at the `enterprise-edge-gateway` Gateway listener in `envoy-gateway-system`. Individual HTTPRoutes no longer carry TLS configuration.
