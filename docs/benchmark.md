# Benchmark Guide

This guide explains how to benchmark a deployed Enterprise Inference environment using the vLLM Benchmark Suite.

## vLLM Benchmark Suite 

[vLLM Benchmark Suite](https://docs.vllm.ai/en/latest/benchmarking/) is the native vLLM Benchmarking tools for vLLM across CPU, HPU, and XPU.
Every new vLLM commit automatically triggers performance runs on multiple platforms, and the results are published on the [vLLM Performance Dashboard](https://hud.pytorch.org/benchmark/llms?repoName=vllm-project%2Fvllm).
Users can run the same Benchmark Suite in their own environment to:

 - Benchmark a deployed Enterprise Inference service
 - Validate expected performance
 - Compare their numbers directly against those published on the dashboard

### Benchmark Enterprise Inference with vLLM Benchmark Suite

#### 1. Obtain the vLLM CI Test Image Matching the Enterprise Inference Version

First, download the vLLM CI test image that corresponds to the vLLM version used in the Enterprise Inference deployment.
Example: download the vLLM CI CPU image for vLLM 0.11.2
```bash 
bash core/scripts/get_vllm_ci_cpu_image.sh 0.11.2
```

Expected output:

```bash 
Using tag: v0.11.2
==> Resolving tag to commit SHA...
Full SHA: 275de34170654274616082721348b7edd9741d32

✅ vLLM CI CPU image for v0.11.2:
public.ecr.aws/q9t5s3a7/vllm-ci-test-repo:275de34170654274616082721348b7edd9741d32-cpu

==> Optional: checking if image is pullable with docker manifest inspect...
Image exists and is pullable.

```

#### 2. Launch the vLLM CI Test Image

Run the CI image interactively to execute benchmarks inside the container.

Example (vLLM 0.11.2 CI CPU image):

```bash
export VLLM_CI_IMAGE=public.ecr.aws/q9t5s3a7/vllm-ci-test-repo:275de34170654274616082721348b7edd9741d32-cpu
docker run -it --entrypoint /bin/bash -v /data/huggingface:/root/.cache/huggingface -v /data:/data -e HF_TOKEN=<YOUR_HF_TOKEN> -e http_proxy=${http_proxy} -e https_proxy=${https_proxy} -e no_proxy=${no_proxy} --shm-size=16g --name vllm-cpu-bench ${VLLM_CI_IMAGE}
```

#### 3. Run Benchmarks Against Your Remote Enterprise Inference Endpoint

3.1 Retrieve the Enterprise Inference Service Endpoint from outside the container: "kubectl get svc". Record the cluster IP and port of the deployed vLLM service. 
3.2 Run the Benchmark Suite from Inside the Container
Set environment variables for your remote endpoint:
```bash
REMOTE_HOST=<VLLM_ENDPOINT_IP> REMOTE_PORT=<VLLM_ENDPOINT_PORT> ON_CPU=1 bash .buildkite/performance-benchmarks/scripts/run-performance-benchmarks.sh
```

The script automatically runs all benchmark cases defined for CPU and generates output files under benchmark/results including:
 - benchmark_results.md — human-readable summary
 - benchmark_results.json — machine-readable detailed results
 - Individual per-test JSON outputs if enabled

For more details, check [manually trigger vllm benchmark suite](https://docs.vllm.ai/en/latest/benchmarking/dashboard/#manually-trigger-the-benchmark)


