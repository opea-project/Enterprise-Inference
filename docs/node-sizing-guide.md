# Node Sizing Guide

This is a guide on how large of a node and how many nodes should be used to deploy Intel® AI for Enterprise Inference. 

## Control Plane Node Sizing
For an inference model deployment cluster in Kubernetes (K8s), the control plane nodes should have sufficient resources to handle the management and orchestration of the cluster. It's recommended to have at least 8 vCPUs and 32 GB of RAM per control plane node.    
For larger clusters or clusters with high workloads, you may need to increase the resources further.

## Workload Node Sizing
The workload node sizing will depend on the specific requirements of the inference models and the workloads they need to handle. Here are some recommendations:

## HPU-based Workloads (Intel® Gaudi®)
For HPU-based inference workloads using Gaudi cards, the workload nodes should be equipped with the appropriate number of Gaudi cards based on the number of models and the expected concurrency. A single Gaudi node has 8 cards.

The workload nodes should also have sufficient RAM and storage capacity to accommodate the inference models and any associated data.

## CPU-based Workloads (Intel® Xeon®)
For CPU-based inference workloads, the workload nodes should have a sufficient number of vCPUs based on the number of models and the expected concurrency. A general guideline is to allocate 32 vCPUs per model instance, depending on the model complexity and resource requirements.

## Infrastructure Node Sizing
Infrastructure nodes used for deploying and managing services like Keycloak and APISIX. The number of nodes required depends on the presence of nodes labeled as    `inference-infra`. If no nodes have this label, a single-node deployment on the control plane node will be used.       
Ensure that sufficient compute resources (CPU, memory, and storage) are provisioned for the infrastructure nodes to handle the expected workloads
### Single-Node Deployment (Fallback)
If no nodes are labeled as `inference-infra` in the `core/inventory/hosts.yaml` file, single replicas of Keycloak and APISIX will be provisioned as a fallback to          support single-node deployment types.

## Node Sizing Guide
For more infromation on node sizing please refer to building large clusters guide
```   
https://kubernetes.io/docs/setup/best-practices/cluster-large/#size-of-master-and-master-components
```

Notice:
It's important to note that these are general recommendations, and the actual sizing may vary based on the specific requirements of your inference models, workloads, and performance expectations.

