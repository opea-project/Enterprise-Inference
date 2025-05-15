
<h1 id="intel-ai-for-enterprise-inference">Intel® AI for Enterprise Inference v1.0.0</h1>

#### Chat completion request [🔗](https://platform.openai.com/docs/api-reference/chat)

<details>
 <summary><code>POST</code> <code><b>/v1/chat/completions</b></code>
</summary>

##### Parameters
`none`


##### Request Body

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[ChatCompletionRequest](https://platform.openai.com/docs/api-reference/chat)|true|none|

##### Response

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|Successful Response|Inline|
|422|Unprocessable Entity|Validation Error|[HTTPValidationError](https://platform.openai.com/docs/guides/error-codes)|

##### Example cURL

 ```bash
curl --location 'https://<base-url>/v1/chat/completions' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer <your-token>' \
--data '{
    "model": "<model-id>",
    "stream": true,
    "stream_options": {
        "include_usage": true
    },
    "temperature": 0,
    "messages": [
        {
            "role": "user",
            "content": "hi"
        }
    ]
}'
```
</details>

#### Completion request [🔗](https://platform.openai.com/docs/api-reference/completions)

<details>
 <summary><code>POST</code> <code><b>/v1/completions</b></code></summary>

##### Parameters
`none`

##### Request Body

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[CompletionRequest](https://platform.openai.com/docs/api-reference/completions)|true|none|

##### Response

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|Successful Response|Inline|
|422|Unprocessable Entity|Validation Error|[HTTPValidationError](https://platform.openai.com/docs/guides/error-codes)|

##### Example cURL

```bash
curl --location 'https://<base-url>/v1/completions' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer <your-token>' \
--data '{
    "model": "<model-id>",
    "prompt": "Once upon a time",
    "stream": true,
    "stream_options": {
        "include_usage": true
    },
    "temperature": 0.7,
    "max_tokens": 100
}'
```
</details>

#### Embedding request [🔗](https://platform.openai.com/docs/api-reference/embeddings)

<details>
 <summary><code>POST</code> <code><b>/v1/embeddings</b></code></summary>

##### Parameters
`none`

##### Request Body

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[EmbeddingRequest](https://platform.openai.com/docs/api-reference/embeddings)|true|none|

##### Response

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|Successful Response|Inline|
|422|Unprocessable Entity|Validation Error|[HTTPValidationError](https://platform.openai.com/docs/guides/error-codes)|

##### Example cURL

```bash
curl --location 'https://<base-url>/v1/embeddings' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer <your-token>' \
--data '{
    "model": "<model-id>",
    "input": "The quick brown fox jumps over the lazy dog",
    "encoding_format": "float"
}'
```
</details>
