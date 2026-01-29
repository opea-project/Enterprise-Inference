# Svara TTS API Server

FastAPI server that integrates VLLM and SNAC for Text-to-Speech.

## Architecture

```
Client Request
    ↓
FastAPI Server (port 8000)
    ↓
VLLM Pod (port 2080) → Tokens
    ↓
SNAC Decoder → PCM16 Audio
    ↓
Client Response
```

## Installation

```bash
cd /home/ubuntu/EI_Stack/Enterprise-Inference/core/tts-api
pip install -r requirements.txt
```

## Configuration

Environment variables:
- `VLLM_URL`: VLLM endpoint (default: `http://10.233.104.79:2080`)
- `API_PORT`: API server port (default: `8000`)

## Running

### Development
```bash
python3 server.py
```

### Production
```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 2
```

### As Background Service
```bash
nohup python3 server.py > /tmp/tts-api.log 2>&1 &
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### List Voices
```bash
curl http://localhost:8000/v1/voices
```

### Text-to-Speech
```bash
curl -X POST http://localhost:8000/v1/text-to-speech \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "en-US-male"}' \
  --output audio.pcm
```

### Play Audio (with ffplay)
```bash
curl -X POST http://localhost:8000/v1/text-to-speech \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}' \
  --output audio.pcm

ffplay -f s16le -ar 24000 -ac 1 audio.pcm
```

## Testing

```bash
# Test health
curl http://localhost:8000/health | jq

# Test voices
curl http://localhost:8000/v1/voices | jq

# Test TTS
curl -X POST http://localhost:8000/v1/text-to-speech \
  -H "Content-Type: application/json" \
  -d '{"text": "Testing one two three"}' \
  --output test.pcm

# Check file size
ls -lh test.pcm
```

## Status Codes

- `200` - Success
- `400` - Bad request (invalid input)
- `503` - Service unavailable (SNAC not loaded)
- `500` - Internal server error

## Next Steps

1. Start the server
2. Test with simple TTS request
3. Verify audio output
4. Deploy to Kubernetes
5. Add monitoring/logging
