# Troubleshooting Guide

This section provides common issues observed when running inference against models deployed via Helm commands on Intel® AI for Enterprise Inference, along with step-by-step resolutions.

**Issues:**
  1. [Gateway Timeout (504) on Inference Requests](#1-gateway-timeout-504-on-inference-requests)

---

### 1. Gateway Timeout (504) on Inference Requests

**Context:** Model deployed via Helm commands. Inference request sent through the ingress stack (ingress-nginx -> APISIX -> vLLM service).

**Error:** Inference requests return `504 Gateway Timeout` after 60 seconds:

```
"POST /<model-name>/v1/completions HTTP/2.0" 504
upstream timed out (110: Operation timed out) ... 60.001
```

**Cause:**

CPU-based model inference (`vllm-cpu`) generates tokens at ~0.3-0.4 tokens/s. Responses requiring more than ~24 tokens exceed the default 60s upstream timeout enforced by ingress-nginx and APISIX.

**Fix:**

**Step 1 - Increase the nginx ingress timeout**

Apply to both the `default` and `auth-apisix` namespaces. To find ingress names:

```bash
kubectl get ingress -A | grep <model-name>
```

Then annotate each ingress:

```bash
kubectl annotate ingress <ingress-name> -n <namespace> \
  nginx.ingress.kubernetes.io/proxy-read-timeout="300" \
  nginx.ingress.kubernetes.io/proxy-send-timeout="300" \
  nginx.ingress.kubernetes.io/proxy-connect-timeout="60" \
  --overwrite
```

**Step 2 - Increase the APISIX route timeout**

To find the route name:

```bash
kubectl get apisixroute -n auth-apisix | grep <model-name>
```

Edit the route:

```bash
kubectl edit apisixroute <route-name> -n auth-apisix
```

Update the timeout section under the route:

```yaml
spec:
  http:
    - name: <route-name>
      timeout:
        connect: 60s
        send: 300s
        read: 300s
```

**Verification:**

Re-run the inference request and confirm a `200 OK` response is returned within the new timeout window.

**Notes:**

- The nginx ingress annotation takes effect immediately; no pod restart required.
- For GPU-based deployments this timeout is rarely needed as throughput is significantly higher (30-50 tokens/s vs 0.3-0.4 tokens/s on CPU).
- If requests still time out after increasing both timeouts, reduce `max_tokens` in the request payload to limit response length.
