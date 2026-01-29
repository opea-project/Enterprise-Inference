"""
FastAPI TTS Server - Integrates VLLM + SNAC for Text-to-Speech
"""
import asyncio
import io
import os
import sys
import time
from typing import Optional, List

import httpx
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

# Add tts_engine to path
sys.path.insert(0, '/home/ubuntu')
from tts_engine.codec import SNACCodec
from tts_engine.constants import SAMPLE_RATE, BIT_DEPTH, AUDIO_TOKEN_OFFSETS

# Configuration
VLLM_URL = os.getenv("VLLM_URL", "http://10.233.104.79:2080")
VLLM_MODEL = "kenpath/svara-tts-v1"
API_PORT = int(os.getenv("API_PORT", "8000"))

# Initialize FastAPI
app = FastAPI(
    title="Svara TTS API",
    description="Text-to-Speech API powered by VLLM and SNAC",
    version="1.0.0"
)

# Global SNAC codec instance (initialized on startup)
snac_codec = None


# Request/Response Models
class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to convert to speech", min_length=1, max_length=500)
    voice: str = Field(default="en-US-male", description="Voice ID to use")
    speed: float = Field(default=1.0, description="Speech speed multiplier", ge=0.5, le=2.0)
    
class VoiceInfo(BaseModel):
    id: str
    name: str
    language: str
    gender: str

class HealthResponse(BaseModel):
    status: str
    vllm_status: str
    snac_loaded: bool
    timestamp: float


# Startup/Shutdown Events
@app.on_event("startup")
async def startup_event():
    """Initialize SNAC codec on startup"""
    global snac_codec
    print("🚀 Starting TTS API Server...")
    print(f"📍 VLLM URL: {VLLM_URL}")
    print(f"🎤 Loading SNAC codec...")
    
    try:
        snac_codec = SNACCodec(device='cpu')
        print(f"✅ SNAC codec loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load SNAC: {e}")
        raise
    
    # Test VLLM connection
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{VLLM_URL}/health")
            if response.status_code == 200:
                print(f"✅ VLLM connection verified")
            else:
                print(f"⚠️ VLLM returned status {response.status_code}")
    except Exception as e:
        print(f"⚠️ Could not verify VLLM connection: {e}")
    
    print("✅ TTS API Server ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Shutting down TTS API Server...")


# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    vllm_status = "unknown"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{VLLM_URL}/health")
            vllm_status = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        vllm_status = "unreachable"
    
    return HealthResponse(
        status="healthy" if snac_codec is not None else "degraded",
        vllm_status=vllm_status,
        snac_loaded=snac_codec is not None,
        timestamp=time.time()
    )


@app.get("/v1/voices", response_model=List[VoiceInfo])
async def list_voices():
    """List available voices"""
    # Placeholder - will be expanded with full voice catalog
    voices = [
        VoiceInfo(id="en-US-male", name="English (US) Male", language="en-US", gender="male"),
        VoiceInfo(id="en-US-female", name="English (US) Female", language="en-US", gender="female"),
    ]
    return voices


@app.post("/v1/text-to-speech")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech
    
    Returns: PCM16 audio data at 24kHz sample rate
    """
    if snac_codec is None:
        raise HTTPException(status_code=503, detail="SNAC codec not initialized")
    
    try:
        # Step 1: Format prompt for VLLM
        prompt = format_tts_prompt(request.text, request.voice)
        
        # Step 2: Call VLLM to get tokens
        tokens = await generate_tokens_from_vllm(prompt)
        
        # Step 3: Extract audio tokens (filter out text tokens)
        audio_tokens = extract_audio_tokens(tokens)
        
        if not audio_tokens:
            raise HTTPException(status_code=500, detail="No audio tokens generated")
        
        # Step 4: Decode tokens to audio using SNAC
        audio_bytes = decode_tokens_to_audio(audio_tokens)
        
        # Step 5: Return audio
        return Response(
            content=audio_bytes,
            media_type="audio/pcm",
            headers={
                "Content-Type": "audio/pcm",
                "X-Sample-Rate": str(SAMPLE_RATE),
                "X-Bit-Depth": str(BIT_DEPTH),
                "X-Channels": "1",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")


# Helper Functions
def format_tts_prompt(text: str, voice: str) -> str:
    """
    Format text into VLLM prompt
    Based on Svara-TTS prompt structure
    """
    # Simplified prompt - will need to be enhanced based on model requirements
    prompt = f"<|im_start|>system\nYou are a text-to-speech system.<|im_end|>\n"
    prompt += f"<|im_start|>user\nConvert to speech: {text}<|im_end|>\n"
    prompt += f"<|im_start|>assistant\n"
    return prompt


async def generate_tokens_from_vllm(prompt: str) -> List[int]:
    """
    Call VLLM API to generate tokens
    """
    payload = {
        "model": VLLM_MODEL,
        "prompt": prompt,
        "max_tokens": 2048,
        "temperature": 0.7,
        "top_p": 0.9,
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{VLLM_URL}/v1/completions",
            json=payload
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"VLLM request failed: {response.text}"
            )
        
        result = response.json()
        
        # Extract token IDs from response
        # Note: This may need adjustment based on actual VLLM response format
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            
            # Try to get token_ids if available
            if "token_ids" in choice and choice["token_ids"]:
                return choice["token_ids"]
            
            # Otherwise, we'd need to tokenize the text response
            # For now, raise an error
            raise HTTPException(
                status_code=500,
                detail="VLLM did not return token IDs. Enable logprobs or token_ids in VLLM config."
            )
        
        raise HTTPException(status_code=500, detail="Invalid VLLM response format")


def extract_audio_tokens(tokens: List[int]) -> List[int]:
    """
    Extract audio tokens from mixed token stream
    Audio tokens are in range [128266, 156938]
    """
    min_audio_token = AUDIO_TOKEN_OFFSETS[0]
    max_audio_token = AUDIO_TOKEN_OFFSETS[-1] + 4096  # Last offset + vocab size
    
    audio_tokens = [
        token for token in tokens
        if min_audio_token <= token <= max_audio_token
    ]
    
    return audio_tokens


def decode_tokens_to_audio(tokens: List[int]) -> bytes:
    """
    Decode audio tokens to PCM16 bytes using SNAC
    """
    audio_bytes = b""
    
    # SNAC expects tokens in groups of 7 (one frame)
    # Process in windows of 7 tokens
    for i in range(0, len(tokens) - 6, 7):
        window = tokens[i:i+7]
        if len(window) == 7:
            try:
                frame_bytes = snac_codec.decode_window(window)
                audio_bytes += frame_bytes
            except Exception as e:
                print(f"⚠️ Failed to decode window {i//7}: {e}")
                continue
    
    return audio_bytes


# Development endpoint for testing
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Svara TTS API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "voices": "/v1/voices",
            "tts": "/v1/text-to-speech"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=API_PORT,
        log_level="info"
    )
