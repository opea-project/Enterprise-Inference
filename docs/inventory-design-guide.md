## Designing Inventory for Inference Cluster Deployment
   
   Design your inventory file located at `core/inventory/hosts.yaml` according to your enterprise deployment requirements for the inference cluster.    

- [Designing Inventory for Inference Cluster Deployment](#designing-inventory-for-inference-cluster-deployment)
   - [Control Plane Node Sizing](#control-plane-node-sizing)
   - [Workload Node Sizing](#workload-node-sizing)
   - [CPU-based Workloads (Intel Xeon)](#cpu-based-workloads-intel-xeon)
   - [HPU-based Workloads (Intel Gaudi)](#hpu-based-workloads-intel-gaudi)
   - [Infrastructure Node Sizing](#infrastructure-node-sizing)
   - [Setting Dedicated Infra Nodes](#setting-dedicated-inference-infra-nodes)
   - [Setting Dedicated Intel Xeon Nodes](#setting-dedicated-inference-xeon-nodes)
   - [Setting Dedicated Intel Gaudi Nodes](#setting-dedicated-gaudi-nodes)
   - [Setting Dedicated Intel CPU Nodes](#setting-dedicated-cpu-nodes)
   - [Node Sizing Guide](#node-sizing-guide)
   - [Single Node Deployment](#single-node-deployment)
   - [Single Master Multiple Workload Node Deployment](#single-master-multiple-workload-node-deployment)
   - [Multi Master Multi Workload Node Deployment](#multi-master-multi-workload-node-deployment)
   - [Multi Master Node with Dedicated Intel Xeon, Gaudi and CPU nodes Deployment](#multi-master-multi-workload-node-with-dedicated-intel-xeon-gaudi-and-cpu-nodes-deployment)

   ##### Control Plane Node Sizing
   For an inference model deployment cluster in Kubernetes (K8s), the control plane nodes should have sufficient resources to handle the management and orchestration of the cluster. It's recommended to have at least 8 vCPUs and 32 GB of RAM per control plane node.    
   For larger clusters or clusters with high workloads, you may need to increase the resources further.
   
   ##### Workload Node Sizing
   The workload node sizing will depend on the specific requirements of the inference models and the workloads they need to handle. Here are some recommendations:
      
   ##### CPU-based Workloads (Intel Xeon)
   For CPU-based inference workloads, the workload nodes should have a sufficient number of vCPUs based on the number of models and the expected concurrency. A general guideline is to allocate 32 vCPUs per model instance, depending on the model complexity and resource requirements.

   ##### HPU-based Workloads (Intel Gaudi)
   For HPU-based inference workloads using Intel Gaudi HPUs, the workload nodes should be equipped with the appropriate number of Gaudi HPUs based on the number of models and the expected concurrency.
   Each Gaudi HPU can handle multiple model instances, depending on the model size and resource requirements.
   
   Additionally, the workload nodes should have sufficient RAM and storage capacity to accommodate the inference models and any associated data.


   ##### Infrastructure Node Sizing
   Infrastructure nodes used for deploying and managing services like Keycloak and APISIX. The number of nodes required depends on the presence of nodes labeled as    `inference-infra`. If no nodes have this label, a single-node deployment on the control plane node will be used.       
   Ensure that sufficient compute resources (CPU, memory, and storage) are provisioned for the infrastructure nodes to handle the expected workloads
   ###### Single-Node Deployment (Fallback)
   If no nodes are labeled as `inference-infra` in the `inventory/hosts.yml` file, single replicas of Keycloak and APISIX will be provisioned as a fallback to          support single-node deployment types.
   
   ##### Node Sizing Guide
   For more infromation on node sizing please refer to building large clusters guide
   ```   
   https://kubernetes.io/docs/setup/best-practices/cluster-large/#size-of-master-and-master-components
   ```

   Notice:
   It's important to note that these are general recommendations, and the actual sizing may vary based on the specific requirements of your inference models, workloads, and performance expectations.

   
   ## Configuring inventory/hosts.yml 

   ##### Note:
   > It is recommended to keep the host names in the `inventory/hosts.yml` file similar to the actual machine hostnames. This ensures compatibility and maintain consistency across different systems and processes. Additionally, this AI Inference Deployment Suite will update the hostnames of the machines to match the ones specified in the `inventory/hosts.yml` file.
   
   ### Setting Dedicated Inference Infra Nodes:   
   To configure dedicated infra node edit the file `inventory/hosts.yml` and add the label `inference-infra` to the nodes.   
   This group will be used to schedule the Keycloak and APISIX workloads.
   
   follow these steps:
   1. Open the `inventory/hosts.yml` file in a text editor.
   2. Locate the section where you define your nodes. This is typically under the `all` group or any other group you've defined for your nodes.
   3. For each node that you want to label as an `inference-infra` node, add the following line under the node's IP or hostname:
   ```yaml
   node_labels:
     node-role.kubernetes.io/inference-infra: "true"
   ```
   4.After labeling the desired nodes, list the nodes under the group kube_inference_infra to include in this group. 

   Please find the template for the inventory configuration with 2 dedicated infra nodes for inference cluster
   ```yaml
      all:
        hosts:
          inference-control-plane-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-infra-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-infra: "true"         
          inference-infra-node-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-infra: "true"
          inference-infra-workload-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key          
        children:
          kube_control_plane:
            hosts:
              inference-control-plane-01:       
          kube_node:
            hosts:
              inference-infra-node-01:
              inference-infra-node-02:
              inference-infra-workload-node-01:    
          kube_inference_infra:
              inference-infra-node-01:
              inference-infra-node-02:
        etcd:
          hosts:
            inference-control-plane-01:       
        k8s_cluster:
          children:
            kube_control_plane:
            kube_node:
            kube_inference_infra: 
   ```

   ### Setting Dedicated Inference Xeon Nodes:   
   To configure a dedicated Xeon nodes for deploying models, edit the file `inventory/hosts.yml` and add the label `inference-xeon` to the nodes.
   This group will be used to schedule the workloads dedicated to run on Xeon nodes.
   
   follow these steps:
   1. Open the `inventory/hosts.yml` file in a text editor.
   2. Locate the section where you define your nodes. This is typically under the `all` group or any other group you've defined for your nodes.
   3. For each node that you want to label as an `inference-xeon`, add the following line under the node's IP or hostname:
   ```yaml
   node_labels:
     node-role.kubernetes.io/inference-xeon: "true"
   ```
   4.After labeling the desired nodes, list the nodes under the group kube_inference_xeon to include in this group. 

   Please find the template for the inventory configuration with 2 dedicated xeon nodes for inference cluster
   ```yaml
      all:
        hosts:
          inference-control-plane-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-xeon-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-xeon: "true"         
          inference-xeon-node-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-xeon: "true"
          inference-infra-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key          
        children:
          kube_control_plane:
            hosts:
              inference-control-plane-01:       
          kube_node:
            hosts:
              inference-xeon-node-01:
              inference-xeon-node-02:
              inference-infra-node-01:
          kube_inference_xeon:
              inference-xeon-node-01:
              inference-xeon-node-02:
        etcd:
          hosts:
            inference-control-plane-01:       
        k8s_cluster:
          children:
            kube_control_plane:
            kube_node:
            kube_inference_xeon: 
   ```


   ### Setting Dedicated Gaudi Nodes:   
   To configure a dedicated Gaudi nodes for deploying models, edit the file `inventory/hosts.yml` and add the label `inference-gaudi` to the nodes.
   This group will be used to schedule the workloads dedicated to run on nodes with Intel Gaudi attached.
   
   follow these steps:
   1. Open the `inventory/hosts.yml` file in a text editor.
   2. Locate the section where you define your nodes. This is typically under the `all` group or any other group you've defined for your nodes.
   3. For each node that you want to label as an `inference-gaudi`, add the following line under the node's IP or hostname:
   ```yaml
   node_labels:
     node-role.kubernetes.io/inference-gaudi: "true"
   ```
   4.After labeling the desired nodes, list the nodes under the group kube_inference_gaudi to include in this group. 

   Please find the template for the inventory configuration with 2 dedicated Gaudi nodes for inference cluster
   ```yaml
      all:
        hosts:
          inference-control-plane-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-gaudi-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-gaudi: "true"         
          inference-gaudi-node-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-xeon: "true"
          inference-infra-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key          
        children:
          kube_control_plane:
            hosts:
              inference-control-plane-01:       
          kube_node:
            hosts:
              inference-gaudi-node-01:
              inference-gaudi-node-02:
              inference-infra-node-01:
          kube_inference_gaudi:
              inference-gaudi-node-01:
              inference-gaudi-node-02:
        etcd:
          hosts:
            inference-control-plane-01:       
        k8s_cluster:
          children:
            kube_control_plane:
            kube_node:
            kube_inference_gaudi: 
   ```

   ### Setting Dedicated CPU Nodes:   
   To configure a dedicated CPU nodes for deploying models, edit the file `inventory/hosts.yml` and add the label `inference-cpu` to the nodes.
   This group will be used to schedule the workloads dedicated to run on nodes with Intel CPUs.
   
   follow these steps:
   1. Open the `inventory/hosts.yml` file in a text editor.
   2. Locate the section where you define your nodes. This is typically under the `all` group or any other group you've defined for your nodes.
   3. For each node that you want to label as an `inference-cpu`, add the following line under the node's IP or hostname:
   ```yaml
   node_labels:
     node-role.kubernetes.io/inference-cpu: "true"
   ```
   4.After labeling the desired nodes, list the nodes under the group kube_inference_cpu to include in this group. 

   Please find the template for the inventory configuration with 2 dedicated CPU nodes for inference cluster
   ```yaml
      all:
        hosts:
          inference-control-plane-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-cpu-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-cpu: "true"         
          inference-cpu-node-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-cpu: "true"
          inference-infra-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key          
        children:
          kube_control_plane:
            hosts:
              inference-control-plane-01:       
          kube_node:
            hosts:
              inference-cpu-node-01:
              inference-cpu-node-02:
              inference-infra-node-01:
          kube_inference_cpu:
              inference-cpu-node-01:
              inference-cpu-node-02:
        etcd:
          hosts:
            inference-control-plane-01:       
        k8s_cluster:
          children:
            kube_control_plane:
            kube_node:
            kube_inference_cpu: 
   ```
   
   ### Single Node Deployment:   
   
   For an single node deployment, ensure that the public SSH key (`id_rsa.pub`) is added to the `authorized_keys` file on the node.  
   This step is necessary to enable the node to establish an SSH connection with itself.   
   Replace the placeholders in the following code with the appropriate values:

   ```yaml
      all:
        hosts:
          inference-control-plane-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key          
        children:
          kube_control_plane:
            hosts:
              inference-control-plane-01:
          kube_node:
            hosts:
              inference-control-plane-01:
          etcd:
            hosts:
              inference-control-plane-01:
          k8s_cluster:
            children:
              kube_control_plane:
              kube_node:
          calico_rr:
            hosts: {}
   ```

 ### Single Master Multiple Workload Node Deployment:   
   
   For deployment with a single control plane node and multiple workload nodes.   
   Replace the placeholders in the following code with the appropriate values:
   
   ```yaml
      all:
        hosts:
          inference-control-plane-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-workload-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-workload-node-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
        children:
          kube_control_plane:
            hosts:
              inference-control-plane-01:
          kube_node:
            hosts:
              inference-workload-node-01:
              inference-workload-node-02:
          etcd:
            hosts:
              inference-control-plane-01:
          k8s_cluster:
            children:
              kube_control_plane:
              kube_node:
          calico_rr:
            hosts: {}
   ```

 ### Multi Master Multi Workload Node Deployment:   
   For an enterprise-grade deployment with multiple control plane nodes and multiple workload nodes, it is recommended to follow these guidelines:
   
   ##### Control Plane Node Count
   It's recommended to have an odd number of control plane nodes (e.g., 3, 5, 7) to ensure high availability and fault tolerance. If one control plane node fails, the remaining nodes can continue to operate and maintain a quorum, ensuring the cluster remains operational.
      
   Replace the placeholders in the following code with the appropriate values:
   
   ```yaml
      all:
        hosts:
          inference-control-plane-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-control-plane-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key         
          inference-control-plane-03:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-workload-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-workload-node-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-workload-node-03:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-workload-node-04:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key         
          inference-workload-node-05:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
        children:
          kube_control_plane:
            hosts:
              inference-control-plane-01:
              inference-control-plane-02:
              inference-control-plane-03:
          kube_node:
            hosts:
              inference-workload-node-01:
              inference-workload-node-02:
              inference-workload-node-03:
              inference-workload-node-04:
              inference-workload-node-05:
          etcd:
            hosts:              
              inference-control-plane-01:
              inference-control-plane-02:
              inference-control-plane-03:
          k8s_cluster:
            children:
              kube_control_plane:
              kube_node:
          calico_rr:
            hosts: {}
   ```

   ### Multi Master Multi Workload Node with Dedicated Intel Xeon, Gaudi and CPU nodes Deployment:   
   For an enterprise-grade deployment with multiple control plane nodes and multiple workload nodes,
   This setup uses workload nodes to be mix of Intel Xeon, Intel Gaudi and Intel CPU nodes for deploying models.
   
   it is recommended to follow these guidelines:
   
   ##### Control Plane Node Count
   It's recommended to have an odd number of control plane nodes (e.g., 3, 5, 7) to ensure high availability and fault tolerance. If one control plane node fails, the remaining nodes can continue to operate and maintain a quorum, ensuring the cluster remains operational.
      
   Replace the placeholders in the following code with the appropriate values:
   
   ```yaml
      all:
        hosts:
          inference-control-plane-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-control-plane-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key         
          inference-control-plane-03:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
          inference-infra-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-infra: "true"
         inference-infra-node-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-infra: "true"         
         inference-infra-node-03:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-infra: "true"
         inference-workload-xeon-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-xeon: "true"
         inference-workload-xeon-node-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-xeon: "true"         
         inference-workload-gaudi-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-gaudi: "true"
         inference-workload-gaudi-node-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-gaudi: "true"
         inference-workload-cpu-node-01:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-cpu: "true"
         inference-workload-cpu-node-02:
            ansible_host: "{{ private_ip }}"
            ansible_user: "{{ ansible_user }}"
            ansible_ssh_private_key_file: /path/to/your/ssh/key
            node_labels:
              node-role.kubernetes.io/inference-cpu: "true"          
        children:
          kube_control_plane:
            hosts:
              inference-control-plane-01:
              inference-control-plane-02:
              inference-control-plane-03:
          kube_node:
            hosts:
              inference-infra-node-01:
              inference-infra-node-02:
              inference-infra-node-03:
              inference-workload-xeon-node-01:
              inference-workload-xeon-node-02:
              inference-workload-gaudi-node-01:
              inference-workload-gaudi-node-02:
              inference-workload-cpu-node-01:
              inference-workload-cpu-node-02:
          etcd:
            hosts:              
              inference-control-plane-01:
              inference-control-plane-02:
              inference-control-plane-03:
         kube_inference_infra:
              inference-infra-node-01:
              inference-infra-node-02:
              inference-infra-node-03:
         kube_inference_xeon:
              inference-workload-xeon-node-01:
	      inference-workload-xeon-node-02:
         kube_inference_gaudi:
              inference-workload-gaudi-node-01:
	      inference-workload-gaudi-node-02:
         kube_inference_cpu:
              inference-workload-cpu-node-01:
	      inference-workload-cpu-node-02:
          k8s_cluster:
            children:
              kube_control_plane:
              kube_node:
              kube_inference_infra:
              kube_inference_xeon:
              kube_inference_gaudi:
              kube_inference_cpu:
          calico_rr:
            hosts: {}

   ```

