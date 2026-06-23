# gpt-oss-20b

This model uses gpt-oss-20b, a 20.9 billion-parameter open-weight mixture-of-experts model from OpenAI. It is part of the gpt-oss family released under the Apache 2.0 license and is optimized for reasoning, agentic workflows, and tool use, with a configurable reasoning effort.

For full details including model specifications, licensing, intended use, safety guidance, and example prompts, please visit the official Hugging Face page: **Official Hugging Face Page**

https://huggingface.co/openai/gpt-oss-20b

This model provides inference services only; weights are hosted by Hugging Face under OpenAI's Apache 2.0 release.

Ensure compliance with OpenAI's Apache 2.0 release terms and usage policy before using this model.

### Model Attribution

**Developer:** OpenAI

**Purpose:** Open-weight reasoning, agentic, and tool-using model with configurable analysis depth (low / medium / high reasoning effort)

**Sizes/Variants:** 20 B total parameters with mixture-of-experts (3.6 B active per token); the gpt-oss family also includes a 120 B variant

**Modalities:** Text input → Text (including code, structured outputs, and tool calls) output

**Parameter Size:** ~20.9 billion total (~3.6 billion active per token)

**Max Context:** Up to 128 k tokens

**License:** Apache 2.0

**Native Quantization:** MXFP4 (4-bit microscaling float) on the MoE weights, dequantized to bf16 at weight-load time for CPU inference

**Minimum required CPU Cores:** 64 (recommended 96+ for usable throughput)

**Minimum required PCIe Cards:** 0 (CPU-only deployment via the patched SGLang Xeon image)

### Usage Notice

**By using this model, you agree that:**

- Inputs and outputs are processed through gpt-oss-20b under OpenAI's Apache 2.0 release.
- You will comply with OpenAI's usage policy and the Apache 2.0 license terms, including attribution and notice requirements when redistributing.
- All generated content (text, code, or tool calls) must be reviewed for accuracy, compliance, and safety before deployment.
- The model should not be used for generating malicious content, disallowed content, or for automating decisions in high-risk or regulated systems without appropriate safeguards.

### Intended Applications

- Reasoning-heavy chatbots and assistants with adjustable reasoning effort.
- Agentic workflows: tool calling, structured function invocation, multi-step task decomposition.
- Code generation, completion, and refactoring across multiple programming languages.
- Long-context tasks: summarization of long documents, dialog over long history, RAG (retrieve-and-generate) over extended context (subject to the long-form notes in the deployment guide).
- Research, prototyping, and commercial workflows under Apache 2.0 terms.

### Limitations

- The 20 B size — while strong for reasoning — still trails much larger models on knowledge-intensive tasks.
- As with all large language models, risk of hallucinations, biases, or unsafe outputs remains; outputs should be reviewed before downstream use.
- The model uses the Harmony chat format with separate analysis and final channels; small `max_tokens` budgets often leave responses in the analysis channel with no user-visible content. See the deployment guide for guidance.
- CPU-only deployment via the patched SGLang image is throughput-limited (~4 tokens/s on a Xeon 6972P with the current pure-Python MoE path) and exhibits a documented long-form drift past ~150 generated tokens. Short-form generation is solid.
- Native MXFP4 quantization requires the patched SGLang image; the upstream `lmsysorg/sglang:v0.5.12-xeon` cannot serve this model.

### References

"Introducing gpt-oss". https://openai.com/index/introducing-gpt-oss/

Hugging Face Model Card: https://huggingface.co/openai/gpt-oss-20b

OpenAI gpt-oss GitHub Repository. https://github.com/openai/gpt-oss
