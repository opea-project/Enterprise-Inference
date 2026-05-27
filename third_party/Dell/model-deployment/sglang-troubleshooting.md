# SGLang Troubleshooting Guide

This section provides common issues observed when running inference against models deployed via the SGLang Helm chart on Intel® AI for Enterprise Inference, along with step-by-step resolutions.

**Issues:**
1. [Gateway Timeout (504) on Inference Requests](#1-gateway-timeout-504-on-inference-requests)
2. [Response `content` field is null](#2-response-content-field-is-null)
3. [Pod startup fails with "Unknown quantization method: mxfp4"](#3-pod-startup-fails-with-unknown-quantization-method-mxfp4)
4. [Pod startup fails with "scalar path not implemented!"](#4-pod-startup-fails-with-scalar-path-not-implemented)
5. [Model serves but emits random-vocab gibberish in `content`](#5-model-serves-but-emits-random-vocab-gibberish-in-content)
6. [Long-form responses degrade into broken tokens after ~150 tokens](#6-long-form-responses-degrade-into-broken-tokens-after-150-tokens)
7. [401 Unauthorized from APISIX with a valid-looking token](#7-401-unauthorized-from-apisix-with-a-valid-looking-token-issuer-mismatch)

---

### 1. Gateway Timeout (504) on Inference Requests

**Context:** Model deployed via the SGLang chart. Inference request sent through the ingress stack (ingress-nginx → APISIX → SGLang service).

**Error:** Inference requests return `504 Gateway Timeout` after 60 seconds.

**Cause:** CPU-based MoE inference (gpt-oss-20b on Xeon) generates tokens at ~4 tokens/s. Responses requiring more than ~240 tokens exceed the default 60s upstream timeout enforced by ingress-nginx and APISIX.

**Fix:**

**Step 1 – Increase the nginx ingress timeout**

Find the ingress and annotate it:

```bash
kubectl get ingress -A | grep sglang
kubectl annotate ingress <ingress-name> -n <namespace> \
  nginx.ingress.kubernetes.io/proxy-read-timeout="600" \
  nginx.ingress.kubernetes.io/proxy-send-timeout="600" \
  nginx.ingress.kubernetes.io/proxy-connect-timeout="60" \
  --overwrite
```

**Step 2 – Increase the APISIX route timeout**

```bash
kubectl get apisixroute -A | grep sglang
kubectl patch apisixroute <route-name> -n <namespace> --type='json' \
  -p='[{"op":"add","path":"/spec/http/0/timeout","value":{"connect":"5s","read":"600s","send":"600s"}}]'
```

**Verification:** Re-run the inference request and confirm a `200 OK` response within the new window.

**Notes:**
- Annotations apply immediately; no pod restart required.
- For shorter responses (`max_tokens ≤ 200`), the default 60s timeout is usually sufficient.

---

### 2. Response `content` field is null

**Context:** gpt-oss-20b deployed via the SGLang chart. Inference request returns HTTP 200 but `choices[0].message.content` is `null`; `choices[0].message.reasoning_content` is populated.

**Cause:** gpt-oss uses the Harmony chat format with separate analysis and final channels. The model always begins in the analysis channel (internal reasoning) and only switches to the final channel when reasoning completes. With small `max_tokens` budgets, the model exhausts the budget while still reasoning and never emits visible content. `finish_reason` will be `length` and `reasoning_tokens` will equal `completion_tokens`.

**Fix:** Raise `max_tokens` so the model has budget to finish reasoning AND emit a final answer:

| `max_tokens` | Outcome                                  |
| ------------ | ---------------------------------------- |
| ≤ 100        | Typically `content: null`                |
| 150          | One short sentence (good for verification) |
| 300          | Paragraph with light formatting          |

The internal reasoning is always preserved in `reasoning_content` even when `content` is null.

---

### 3. Pod startup fails with "Unknown quantization method: mxfp4"

**Context:** Pod CrashLoopBackOff at startup. Logs show `ValueError: Unknown quantization method: mxfp4`.

**Cause:** The pod is running the upstream `lmsysorg/sglang:v0.5.12-xeon` image. The upstream image gates MXFP4 quantization behind `is_cuda() or is_hip()`, so it cannot load MXFP4 models on CPU.

**Fix:** Confirm the chart is using the patched image. The chart's `values.yaml` defaults to it, but a `--set image.repository=...` override may have switched it back:

```bash
kubectl get pod -l app=sglang -o jsonpath='{.items[0].spec.containers[0].image}{"\n"}'
# expected: enterprise-inference/sglang:v0.5.12-xeon-fix11-debug
```

If the image is wrong, redeploy with the chart defaults or explicitly set:

```bash
helm upgrade <release> ./core/helm-charts/sglang \
  --reuse-values \
  --set image.repository=enterprise-inference/sglang \
  --set image.tag=v0.5.12-xeon-fix11-debug
```

If the patched image is not present locally, build it first:

```bash
sudo bash core/helm-charts/sglang/image-build/build-and-import.sh
```

---

### 4. Pod startup fails with "scalar path not implemented!"

**Context:** Pod crashes on the first forward pass. Logs show `RuntimeError: tinygemm_kernel_nn: scalar path not implemented!`.

**Cause:** The `sgl-kernel` shared library loaded by the pod was compiled without `-mavx512bf16`. The bf16 specialization of `tinygemm_kernel_nn` falls through to a stub that throws this error. This is the upstream regression the patched image's Dockerfile step 1 fixes.

**Fix:** Verify the patched image is loaded (same check as issue #3). If the patched image is loaded and this error still appears, the build may have failed silently — rebuild and check the verification line:

```bash
sudo bash core/helm-charts/sglang/image-build/build-and-import.sh 2>&1 | grep "AVX-512 BF16 instructions"
# expected: ~1400+ instructions
```

A count under 100 indicates the compile flags did not take effect during the build.

---

### 5. Model serves but emits random-vocab gibberish in `content`

**Context:** gpt-oss-20b deployed. Inference returns HTTP 200, `content` is non-null but looks like a sequence of unrelated tokens (e.g., `" the I the and a"`).

**Cause:** MXFP4 weights are being dequantized with the wrong nibble packing order. gpt-oss stores its MXFP4 weights with the low nibble first; the patched image's dequant defaults to this via the `MXFP4_NIBBLE_ORDER` environment variable.

**Fix:** Verify the env var is set on the pod:

```bash
kubectl get pod -l app=sglang -o jsonpath='{range .items[0].spec.containers[0].env[*]}{.name}={.value}{"\n"}{end}' | grep MXFP4_NIBBLE_ORDER
# expected: MXFP4_NIBBLE_ORDER=low_first
```

The chart's `values.yaml` includes this default. If it is missing, redeploy without overriding `extraEnv` to an empty list.

---

### 6. Long-form responses degrade into broken tokens after ~150 tokens

**Context:** gpt-oss-20b deployed via the SGLang chart. Short-form responses are coherent. Responses past ~150 generated tokens collapse into broken tokens, repeated characters, mixed emoji, foreign-script characters, or special-token leaks like `<|channel|>` appearing in the visible output.

**Cause:** Known limitation of the current pure-Python CPU MoE path used by the chart. A precision A/B (fp32 per-expert MoE intermediates, fp32 KV cache, `--enable-fp32-lm-head`) ruled out numerical precision as the dominant cause. Surviving hypotheses point at sliding-window-attention bookkeeping inside the patched `torch_native_backend` or Harmony channel-switch tokenization interacting with the sinks-attention wrapper.

**Fix:** No fix at the chart level yet. Workarounds:
- Keep `max_tokens` at or below 200 for production calls.
- Phrase prompts to produce short, focused answers (e.g., `"In one sentence, ..."`).
- The internal `reasoning_content` is unaffected and can still be inspected.

This is documented under "Known Limitations" in `core/helm-charts/sglang/README.md`. Long-form coherence requires further work on the attention or channel-switch path.

---

### 7. 401 Unauthorized from APISIX with a valid-looking token (issuer mismatch)

**Context:** Token was successfully obtained from Keycloak (via `source generate-token.sh` or equivalent), but the inference call returns `401 Unauthorized` from APISIX (response body mentions "openresty").

**Cause:** APISIX's OIDC plugin runs in `bearer_only` mode and validates the token's `iss` (issuer) claim against the issuer returned by the OIDC discovery URL the chart was configured with. If Keycloak was deployed without a fixed `KC_HOSTNAME`, it stamps the issuer based on the incoming request's host header — so a token fetched via `https://api.example.com:30443/token` carries `iss=https://api.example.com:30443/realms/master`, but the chart's default discovery URL is `http://keycloak.default.svc.cluster.local/realms/master`. The two don't match and APISIX rejects.

**Fix:** Pin Keycloak's issuer at deploy time by setting `KC_HOSTNAME` on the Keycloak Deployment to the cluster-internal hostname the chart's `oidc.discovery` value points at. The appendix in `core/helm-charts/sglang/README.md` (A.3) shows the env vars; the relevant ones are:

```yaml
- { name: KC_HOSTNAME,             value: "http://keycloak.default.svc.cluster.local" }
- { name: KC_HOSTNAME_STRICT,      value: "false" }
- { name: KC_HOSTNAME_BACKCHANNEL_DYNAMIC, value: "false" }
```

After updating the Deployment (`kubectl apply` the manifest from A.3 again, then wait for the new pod), re-source `generate-token.sh` to fetch a fresh token. Verify the issuer claim is now cluster-internal:

```bash
echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null \
  | python3 -c "import json,sys; print('iss =', json.loads(sys.stdin.read())['iss'])"
# expect: iss = http://keycloak.default.svc.cluster.local/realms/master
```

The mismatched-issuer 401 cannot happen on a production EI cluster — the Ansible playbooks set `KC_HOSTNAME` to the cluster's external hostname and the chart's `oidc.discovery` is set to the matching URL — but it's a common stumble for someone bootstrapping by hand from the appendix.
