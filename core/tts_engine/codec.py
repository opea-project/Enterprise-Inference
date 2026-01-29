"""
CPU-Optimized SNAC Codec for Intel Xeon processor.

This module provides efficient SNAC encoding/decoding for text-to-speech synthesis
on CPU-only systems. Optimized for Intel Xeon processors with MKL and OpenMP support.
"""

import torch
import numpy as np
from typing import List, Optional
from snac import SNAC
from .constants import AUDIO_TOKEN_OFFSETS
import logging

logger = logging.getLogger(__name__)

# Global model cache to avoid reloading SNAC model for each instance
_SNAC_MODEL_CACHE: dict[str, SNAC] = {}


def _get_or_load_snac_model(device: str, model_name: str = "hubertsiuzdak/snac_24khz") -> SNAC:
    """
    Get cached SNAC model or load it if not cached.
    
    This prevents repeated model loading when creating multiple codec instances.
    Models are cached per device to handle scenarios with different devices.
    
    Args:
        device: Device to load model on ('cpu', 'cuda', 'mps')
        model_name: HuggingFace model identifier
    
    Returns:
        Cached or newly loaded SNAC model
    """
    cache_key = f"{model_name}_{device}"
    
    if cache_key not in _SNAC_MODEL_CACHE:
        logger.info(f"Loading SNAC model: {model_name} on device: {device}")
        model = SNAC.from_pretrained(model_name).eval().to(device)
        logger.info(f"SNAC model loaded on {device}")
        _SNAC_MODEL_CACHE[cache_key] = model
    else:
        logger.debug(f"Using cached SNAC model: {cache_key}")
    
    return _SNAC_MODEL_CACHE[cache_key]


class SNACCodec:
    """
    CPU-optimized SNAC codec for encoding audio to tokens and decoding tokens to audio.
    
    Specifically optimized for Intel Xeon CPUs with:
    - MKL-BLAS acceleration (Intel Math Kernel Library)
    - OpenMP multi-threading
    - CPU-specific inference optimizations
    
    Features:
    - Encoding: audio waveform → SNAC tokens
    - Decoding: SNAC tokens → PCM16 audio
    - Global model caching to avoid reloads
    - Efficient memory usage on CPU
    """
    
    def __init__(self, device: Optional[str] = None, model_name: str = "hubertsiuzdak/snac_24khz"):
        """
        Initialize SNAC codec with CPU optimization.
        
        Args:
            device: Device to use ('cpu', 'cuda', 'mps', or None for auto-detect)
                   None defaults to CPU if CUDA unavailable
            model_name: HuggingFace model identifier for SNAC
        """
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        
        self.device = device
        self.model_name = model_name
        self.sample_rate = 24000  # SNAC 24kHz model
        
        logger.info(f"Initializing SNAC codec on device: {device}")
        
        # Get or load model from cache
        self.model = _get_or_load_snac_model(device, model_name)
        
        # Optimize for CPU inference
        if device == "cpu":
            self._optimize_for_cpu()
    
    def _optimize_for_cpu(self):
        """Apply CPU-specific optimizations for Intel Xeon."""
        # Enable PyTorch CPU optimization
        torch.set_float32_matmul_precision('high')
        
        # MKL optimizations
        if torch.backends.mkl.is_available():
            torch.backends.mkl.benchmark = True
            logger.info("MKL optimization enabled")
        
        # OpenMP optimization (already uses all available threads)
        num_threads = torch.get_num_threads()
        logger.info(f"OpenMP threads available: {num_threads}")

    def encode_audio(
        self,
        audio: torch.Tensor,
        input_sample_rate: int = 24000,
        add_token_offsets: bool = True
    ) -> List[int]:
        """
        Encode audio waveform to SNAC tokens.
        
        Args:
            audio: Audio tensor of shape (channels, samples) or (samples,).
                   If 1D, will be converted to (1, 1, samples).
            input_sample_rate: Sample rate of input audio in Hz. 
                              If not 24000, audio will be resampled.
            add_token_offsets: If True, adds Svara-TTS token offsets (128266+).
                              If False, returns raw SNAC codes [0, 4096].
        
        Returns:
            List of token IDs (7 tokens per frame).
        
        Example:
            >>> codec = SNACCodec()
            >>> audio = torch.randn(24000)  # 1 second at 24kHz
            >>> tokens = codec.encode_audio(audio)
            >>> len(tokens)  # ~700 tokens (100 frames × 7)
        """
        # Ensure proper shape: SNAC expects (batch, channels, samples)
        if audio.dim() == 1:
            # (samples,) -> (1, 1, samples)
            audio = audio.unsqueeze(0).unsqueeze(0)
        elif audio.dim() == 2:
            # (channels, samples) -> (1, channels, samples)
            audio = audio.unsqueeze(0)
        
        # Move to device and ensure float32
        audio = audio.to(dtype=torch.float32, device=self.device)
        
        logger.debug(f"Encoding audio shape: {audio.shape}")
        
        # Encode with SNAC
        with torch.inference_mode():
            codes = self.model.encode(audio)
        
        # SNAC produces hierarchical codes:
        # codes[0]: coarsest (e.g., 100 frames for 1 sec)
        # codes[1]: 2x finer (e.g., 200 frames)
        # codes[2]: 4x finer (e.g., 400 frames)
        
        all_codes = []
        num_coarse_frames = codes[0].shape[1]
        
        for i in range(num_coarse_frames):
            c0 = codes[0][0][i].item()
            c1 = codes[1][0][2 * i].item()
            c2 = codes[2][0][4 * i].item()
            c3 = codes[2][0][4 * i + 1].item()
            c4 = codes[1][0][2 * i + 1].item()
            c5 = codes[2][0][4 * i + 2].item()
            c6 = codes[2][0][4 * i + 3].item()
            
            if add_token_offsets:
                # Add Svara-TTS vocabulary offsets
                all_codes.append(c0 + AUDIO_TOKEN_OFFSETS[0])
                all_codes.append(c1 + AUDIO_TOKEN_OFFSETS[1])
                all_codes.append(c2 + AUDIO_TOKEN_OFFSETS[2])
                all_codes.append(c3 + AUDIO_TOKEN_OFFSETS[3])
                all_codes.append(c4 + AUDIO_TOKEN_OFFSETS[4])
                all_codes.append(c5 + AUDIO_TOKEN_OFFSETS[5])
                all_codes.append(c6 + AUDIO_TOKEN_OFFSETS[6])
            else:
                # Raw SNAC codes
                all_codes.extend([c0, c1, c2, c3, c4, c5, c6])
        
        logger.debug(f"Encoded to {len(all_codes)} tokens ({num_coarse_frames} frames)")
        return all_codes
    
    def decode_window(self, window: List[int]) -> bytes:
        """
        Decode a window of Svara-TTS codes into PCM16 bytes.
        
        Optimized for CPU inference with efficient tensor operations.
        
        Args:
            window: Flat list of int codes, length multiple of 7.
                   Should be raw SNAC codes in range [0, 4096],
                   NOT with token offsets added.
        
        Returns:
            PCM16 mono bytes; empty bytes if invalid input.
        """
        if not window or len(window) < 7:
            logger.warning(f"Invalid window size: {len(window)}")
            return b""
        
        # Use only full frames
        F = len(window) // 7
        frame = window[: F * 7]
        
        # Build code streams: [c0], [c1,c4], [c2,c3,c5,c6]
        t = torch.tensor(frame, dtype=torch.int32, device=self.device)
        t = t.view(F, 7)
        
        codes_0 = t[:, 0].reshape(1, -1)
        codes_1 = t[:, [1, 4]].reshape(1, -1)
        codes_2 = t[:, [2, 3, 5, 6]].reshape(1, -1)
        
        # Validate range [0, 4096]
        if (
            torch.any((codes_0 < 0) | (codes_0 > 4096)) or
            torch.any((codes_1 < 0) | (codes_1 > 4096)) or
            torch.any((codes_2 < 0) | (codes_2 > 4096))
        ):
            logger.error("Code values out of valid range [0, 4096]")
            return b""
        
        with torch.inference_mode():
            audio = self.model.decode([codes_0, codes_1, codes_2])  # [1, 1, T]
            # Keep the synthesis region (2048:4096 samples per frame)
            audio = audio[:, :, 2048:4096]
        
        # Convert to PCM16 bytes
        x = audio.detach().float().cpu().numpy().reshape(-1)
        pcm16 = (np.clip(x, -1.0, 1.0) * 32767.0).astype(np.int16)
        
        logger.debug(f"Decoded {len(frame)//7} frames to {len(pcm16)} samples")
        return pcm16.tobytes()
    
    def get_device(self) -> str:
        """Get the device this codec is using."""
        return self.device
    
    def get_model_size(self) -> int:
        """Get approximate model size in MB."""
        param_count = sum(p.numel() for p in self.model.parameters())
        # Approximate 4 bytes per parameter (float32)
        size_mb = (param_count * 4) / (1024 * 1024)
        return int(size_mb)
