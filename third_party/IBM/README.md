# Intel AI for Enterprise Inference as a Deployable Architecture on IBM Cloud
Enterprise Inference deployments follow IBM Cloud's deployable architecture pattern .Use this to automate the process of VM spin up, manage installation of Intel Gaudi operators and LLM model bring-up on K8S cluster using Terraform referring to OPEA's Enterprise Inference framework.

## Overview
This solution leverages Terraform to automate the deployment of virtual machines on IBM Cloud, specifically tailored for AI workloads using Intel Xeon/Gaudi hardware. It installs all necessary Intel Gaudi-specific operators and deploys large language models (LLMs) using OPEA's Enterprise Inference framework. By integrating cutting-edge AI infrastructure with cloud automation, this solution provides a streamlined approach to deploying and managing complex machine learning models in a scalable and efficient manner. Ideal for those who are looking to harness the power of AI with minimal setup time and maximum performance.

[Setup Instructions](enterprise_inference.md)

## 📁 Directory Structure
```
repo/
├── .bluemix/
│ ├── deploy.json # Defines user input parameters shown in the UI during deployment
│ └── pipeline.yml # (Optional) Defines DevOps toolchain pipeline template
│ └── toolchain.yml # (Optional) Based on what’s defined here it spins up a toolchain in IBM DevOps
├── patterns/(quickstart or standard)/main.tf # Main Terraform configuration file for resource definitions
├── patterns/(quickstart or standard)/variables.tf # Declares input variables referenced in Terraform code
├── patterns/(quickstart or standard)/run_script # A shell script containing post-deployment configuration commands. It is copied and executed on the target vsi after provisioning via Terraform using `remote-exec`.
├── ibm_catalog.json # Metadata file for registering in IBM Cloud Private Catalog
```

## Sizing Chart for Gaudi3 nodes
To provide a clear understanding of the sizing requirements, we've compiled tables that detail the number of accelerators needed and the expected throughput for different configurations. 

**Table 1: Sizing for Small Models (1B – 40B Tokens) – Single HPU execution**:
For models with 1 billion tokens and smaller token configurations, a single Gaudi3 node with a batch size of 1 can deliver satisfactory throughput. Scaling up to batch sizes of 4 or 16 can significantly improve performance, with the need for additional accelerators as token sizes increase. 

```
| HPUs  | Model  Size (B)  | Input Tokens  | Output Tokens  | Batch Size  | Precision  | Throughput  (tokens/sec)  |
|-------|------------------|---------------|----------------|-------------|------------|---------------------------|
| 1     | 1                | 32            | 32             | 1           | 16-bit     | 528                       |
| 1     | 1                | 32            | 32             | 4           | 16-bit     | 2049                      |
| 1     | 1                | 32            | 32             | 16          | 16-bit     | 7093                      |
| 1     | 1                | 32            | 128            | 16          | 16-bit     | 8902                      |
| 1     | 1                | 32            | 512            | 16          | 16-bit     | 8582                      |
| 1     | 1                | 32            | 1024           | 16          | 16-bit     | 8032                      |
| 1     | 1                | 32            | 2048           | 16          | 16-bit     | 7077                      |
| 1     | 1                | 32            | 4096           | 16          | 16-bit     | 3680                      |
| 1     | 1                | 32            | 8192           | 1           | 16-bit     | 504                       |
| 1     | 1                | 32            | 8192           | 4           | 16-bit     | 1332                      |
| 1     | 1                | 8192          | 8192           | 1           | 16-bit     | 504                       |
| 1     | 1                | 8192          | 8192           | 4           | 16-bit     | 1337                      |
| 1     | 1.5              | 32            | 8192           | 1           | 16-bit     | 299                       |
| 1     | 1.5              | 1024          | 1024           | 1           | 16-bit     | 278                       |
| 1     | 1.5              | 8192          | 32             | 1           | 16-bit     | 342                       |
| 1     | 1.5              | 8192          | 32             | 4           | 16-bit     | 1340                      |
| 1     | 1.5              | 8192          | 32             | 16          | 16-bit     | 4637                      |
| 1     | 3                | 32            | 512            | 16          | 16-bit     | 4074                      |
| 1     | 3                | 128           | 4096           | 16          | 16-bit     | 1861                      |
| 1     | 3                | 1024          | 32             | 16          | 16-bit     | 3683                      |
| 1     | 3                | 4096          | 2048           | 16          | 16-bit     | 3220                      |
| 1     | 3                | 8192          | 2048           | 16          | 16-bit     | 3220                      |
| 1     | 7                | 32            | 128            | 16          | 16-bit     | 2146                      |
| 1     | 7                | 1024          | 128            | 16          | 16-bit     | 2523                      |
| 1     | 7                | 4096          | 32             | 16          | 16-bit     | 2017                      |
| 1     | 8                | 32            | 4096           | 16          | 16-bit     | 1288                      |
| 1     | 8                | 128           | 128            | 16          | 16-bit     | 2447                      |
| 1     | 8                | 8192          | 128            | 16          | 16-bit     | 2445                      |
| 1     | 8                | 8192          | 512            | 16          | 16-bit     | 1735                      |
| 1     | 13               | 32            | 32             | 16          | 16-bit     | 1330                      |
| 1     | 13               | 32            | 128            | 16          | 16-bit     | 1413                      |
| 1     | 13               | 128           | 128            | 16          | 16-bit     | 1408                      |
| 1     | 13               | 128           | 512            | 16          | 16-bit     | 1261                      |
| 1     | 13               | 2048          | 32             | 16          | 16-bit     | 1321                      |
| 1     | 13               | 2048          | 512            | 16          | 16-bit     | 1262                      |
| 1     | 13               | 8192          | 1024           | 16          | 16-bit     | 1077                      |
| 1     | 14               | 512           | 32             | 16          | 16-bit     | 1270                      |
| 1     | 14               | 1024          | 512            | 16          | 16-bit     | 1220                      |
| 1     | 14               | 2048          | 128            | 16          | 16-bit     | 1221                      |
| 1     | 14               | 8192          | 512            | 16          | 16-bit     | 1221                      |
| 1     | 40               | 128           | 512            | 16          | 16-bit     | 346                       |
| 1     | 40               | 128           | 1024           | 16          | 16-bit     | 350                       |
| 1     | 40               | 512           | 32             | 16          | 16-bit     | 444                       |
| 1     | 40               | 512           | 1024           | 16          | 16-bit     | 350                       |
| 1     | 40               | 8192          | 1024           | 16          | 16-bit     | 347                       |
```
**Table 2 : Larger models 40B-72B ( 2-4 HPU Execution )**:
Medium-sized models benefit from multiple accelerators, especially when using larger token configurations. A combination of 2-4 Gaudi3 nodes can optimize throughput for batch sizes of 4 or 16, ensuring efficient processing. 
```
| HPUs  | Model  Size (B)  | Input Tokens  | Output Tokens  | Batch Size  | Precision  | Throughput  (tokens/sec)  |
|-------|------------------|---------------|----------------|-------------|------------|---------------------------|
| 2     | 40               | 32            | 512            | 16          | 16-bit     | 674                       |
| 2     | 40               | 128           | 32             | 16          | 16-bit     | 633                       |
| 2     | 67               | 32            | 1024           | 16          | 16-bit     | 455                       |
| 2     | 67               | 32            | 32             | 16          | 16-bit     | 485                       |
| 2     | 67               | 32            | 128            | 16          | 16-bit     | 472                       |
| 3     | 72               | 32            | 32             | 16          | 16-bit     | 519                       |
| 3     | 72               | 32            | 128            | 16          | 16-bit     | 527                       |
| 4     | 40               | 32            | 1024           | 16          | 16-bit     | 1008                      |
| 4     | 67               | 512           | 128            | 16          | 16-bit     | 741                       |
| 4     | 67               | 512           | 1024           | 16          | 16-bit     | 713                       |
```
**Table 3 : Big models**
Large models require significant computational power. Deploying 4 or more Gaudi3 nodes is recommended to handle high token counts and batch sizes, ensuring maximum throughput and efficiency. 
```
| HPUs  | Model  Size (B)  | Input Tokens  | Output Tokens  | Batch Size  | Precision  | Throughput  (tokens/sec)  |
|-------|------------------|---------------|----------------|-------------|------------|---------------------------|
| 8     | 405B             | 512           | 32             | 4           | FP8        | 77                        |
| 8     | 405B             | 512           | 128            | 4           | FP8        | 81                        |
| 8     | 405B             | 512           | 512            | 4           | FP8        | 80                        |
```
