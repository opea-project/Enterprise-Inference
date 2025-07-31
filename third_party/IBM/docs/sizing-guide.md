# Introducing the Intel® Gaudi® 3 AI Accelerator: Powering the Next Wave of Enterprise AI

The Intel® Gaudi® 3 AI accelerator emerges as a compelling force in the rapidly evolving landscape of artificial intelligence, specifically designed to address the increasing demands of demanding AI workloads, particularly in the realm of large language models (LLMs) and generative AI.

Built on a foundation of high-performance and efficiency, the Gaudi 3 represents a significant leap forward from its predecessor, the Gaudi 2. Engineered with advanced capabilities, including enhanced compute power, expanded memory capacity, and integrated, high-speed Ethernet networking, Gaudi 3 positions itself as a competitive and powerful solution for enterprises aiming to scale their AI infrastructure.

## Key Features

Key features of the Intel Gaudi 3 AI Accelerator include:

- **Powerful Compute Engines**: A heterogeneous compute architecture featuring 64 Tensor Processor Cores (TPCs) and 8 Matrix Multiplication Engines (MMEs) delivers substantial computational power for diverse AI applications.

- **Enhanced Memory**: Boasting 128 GB of HBM2e memory with a bandwidth of 3.7 TB/s, Gaudi 3 efficiently handles memory-intensive workloads like LLM training and inference.

- **Scalable Networking**: Integrated 24x 200GbE Ethernet ports enable flexible and massive system scaling, utilizing standard Ethernet infrastructure, and offering an alternative to proprietary solutions.

- **Open Software Ecosystem**: Support for popular open-source frameworks like PyTorch and readily available optimized models on Hugging Face facilitates easy adoption and model porting.

## Benefits

With its focus on performance, scalability, and cost-efficiency, the Intel Gaudi 3 AI accelerator empowers enterprises to:

- **Accelerate AI Training and Inference**: Gaudi 3 promises substantial performance improvements for both training and inference tasks on leading GenAI models.

- **Scale AI Workloads with Ease**: The flexible and open-standard Ethernet networking enables efficient scaling from single nodes to thousands of accelerators.

- **Benefit from Competitive Price Performance**: Gaudi 3 is positioned as a cost-effective alternative to existing solutions in the market, offering compelling price-performance advantages.

The Intel Gaudi 3 AI accelerator is poised to play a crucial role in enabling enterprises to unlock new insights, drive innovation, and capitalize on the opportunities presented by generative AI and other complex AI workloads.

More details in the [Intel® Gaudi® 3 AI Accelerator White Paper](https://www.intel.com/content/www/us/en/content-details/817486/intel-gaudi-3-ai-accelerator-white-paper.html).

## Understanding AI Model Hosting Requirements

The CPU on the Gaudi 3 servers may feature 5th Gen Intel® Xeon® processors with up to 64 cores, along with 8 Habana Processing Units (HPUs), generally also has more than 8TB of storage on the device packs a powerful package for AI processing. Efficient usage of the infrastructure is important for a better return on investment. In the table below we provide a view of resources needed for hosting models of various sizes.

| Model Size | Example Models | HPUs needed for hosting |
|------------|----------------|------------------------|
| 1B-32B | meta-llama/Llama-3.1-8B-Instruct | 1 HPU card (i.e.) 1/8th of a Gaudi server |
| 64-180B | meta-llama/Llama-3.3-70B-Instruct | 4 HPU cards (i.e.) 1/2 of a Gaudi server |
| 180B-405B | meta-llama/Llama-3.1-405B-Instruct | 8 HPU cards (i.e.) Full Gaudi Server |

## Performance Metrics

Based on the configuration specified in the previous Model Hosting section, the following performance metrics can be observed, based on the inputs and outputs expected from the models.

The exact performance is dependent on the software stack and the hardware drivers installed, other than the hardware configuration. Published Gaudi 3 results are on vllm v0.7.2+Gaudi-1.21.0. All the numbers that are provided in the tables below are based on a single replica being run on the instance. For example, the 8B model uses only one of the HPU cards, hence just 1/8th of a 8 HPU instance being used for the experiment. One can host 8 such replicas on the same instance. Similarly, if any model uses 4 HPU cards, then one can host 2 such replicas on the 8 HPU instance. Here is a use-case based analysis of performance. The input and output tokens are per user. The sweet spots were chosen based on acceptable Time to First Token(TTFT) wherein increasing the number of concurrent users even by one increases the TTFT by a large amount.

### 8B model (meta-llama/Llama-3.1-8B-Instruct) sweet spots (with a single instance – 1 HPU)

| Use Case | Input Tokens | Output Tokens | Concurrent Users | Throughput per User (Tokens/sec) | TTFT in ms (p90) | SLA |
|----------|--------------|---------------|------------------|----------------------------------|------------------|-----|
| Chatbot | 128 | 128 | 65 | 3264 | 1300 | <=2s |
| Content Creation | 128 | 2048 | 35 | 3172 | 394 | <=10s |
| Code Generation | 128 | 4096 | 35 | 2799 | 474 | <=10s |
| Describe | 2048 | 128 | 210 | 1318 | 19463 | <=20s |
| Suggest | 4096 | 128 | 135 | 800 | 18745 | <=20s |
| Summarize | 8192 | 128 | 65 | 391 | 18412 | <=20s |
| Translate | 1024 | 1024 | 65 | 2854 | 11815 | <=20s |
| Correct | 2048 | 2048 | 35 | 2463 | 1921 | <=20s |

### 70B model (meta-llama/Llama-3.3-70B-Instruct) sweet spots (with a single instance – 4 HPUs)

| Use Case | Input Tokens | Output Tokens | Concurrent Users | Throughput per User (Tokens/sec) | TTFT in ms (p90) | SLA |
|----------|--------------|---------------|------------------|----------------------------------|------------------|-----|
| Chatbot | 128 | 128 | 35 | 1120 | 613 | <=2s |
| Content Creation | 128 | 2048 | 35 | 1269 | 586 | <=10s |
| Code Generation | 128 | 4096 | 35 | 1254 | 605 | <=10s |
| Describe | 2048 | 128 | 65 | 486 | 13348 | <=20s |
| Suggest | 4096 | 128 | 40 | 306 | 18123 | <=20s |
| Summarize | 8192 | 128 | 30 | 161 | 19952 | <=20s |
| Translate | 1024 | 1024 | 35 | 1158 | 3320 | <=20s |
| Correct | 2048 | 2048 | 60 | 1060 | 7589 | <=20s |

### 405B model (meta-llama/Llama-3.1-405B-Instruct) sweet spots (with a single instance – 8 HPUs)

| Use Case | Input Tokens | Output Tokens | Concurrent Users | Throughput per User (Tokens/sec) | TTFT in ms (p90) | SLA |
|----------|--------------|---------------|------------------|----------------------------------|------------------|-----|
| Chatbot | 128 | 128 | 35 | 493 | 1072 | <=2s |
| Content Creation | 128 | 2048 | 35 | 557 | 1193 | <=10s |
| Code Generation | 128 | 4096 | 35 | 534 | 1147 | <=10s |
| Describe | 2048 | 128 | 35 | 165 | 17739 | <=20s |
| Suggest | 4096 | 128 | 20 | 103 | 17675 | <=20s |
| Summarize | 8192 | 128 | 130 | 472 | 18992 | <=20s |
| Translate | 1024 | 1024 | 35 | 462 | 17576 | <=20s |
| Correct | 2048 | 2048 | 35 | 493 | 1072 | <=20s |

## Conclusion

Intel Gaudi3 nodes offer a powerful solution for AI practitioners looking to optimize their model performance. By understanding the relationship between model size, token configuration, batch size, and accelerator requirements, you can make strategic decisions that enhance your AI capabilities. Whether you're working with small or large models, this sizing guide provides the insights needed to harness the full potential of Gaudi3 nodes and achieve exceptional throughput.

Stay tuned for more updates and insights as we continue to explore the capabilities of Intel's cutting-edge technology in the world of artificial intelligence.