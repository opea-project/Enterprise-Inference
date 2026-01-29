"""
Utilities for SNAC codec and TTS engine.
"""

import torch
import torchaudio
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def resample_audio(
    audio: torch.Tensor,
    original_sr: int,
    target_sr: int,
    device: Optional[str] = None,
) -> torch.Tensor:
    """
    Resample audio to a target sample rate using torchaudio.
    
    Optimized for both GPU and CPU inference.
    
    Args:
        audio: Audio tensor of shape (channels, samples) or (samples,).
               If 1D, will be converted to (1, samples).
        original_sr: Original sample rate in Hz.
        target_sr: Target sample rate in Hz.
        device: Device to use ('cuda', 'cpu', or None for auto-detect).
    
    Returns:
        Resampled audio tensor with shape matching input.
    
    Example:
        >>> audio = torch.randn(1, 48000)  # 1 second at 48kHz
        >>> resampled = resample_audio(audio, 48000, 24000)
        >>> resampled.shape
        torch.Size([1, 24000])
    """
    # Handle device
    if device is None:
        if torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"
    
    # Ensure audio is 2D
    if audio.dim() == 1:
        audio = audio.unsqueeze(0)
    
    # Move to target device
    audio = audio.to(device)
    
    # If already at target sample rate, return as-is
    if original_sr == target_sr:
        return audio
    
    # Create resampler
    resampler = torchaudio.transforms.Resample(original_sr, target_sr, dtype=audio.dtype)
    resampler = resampler.to(device)
    
    # Resample
    resampled = resampler(audio)
    
    logger.debug(f"Resampled from {original_sr} to {target_sr}Hz: {audio.shape} -> {resampled.shape}")
    
    return resampled


def clip_to_int16(audio: torch.Tensor) -> torch.Tensor:
    """
    Clip and convert audio to int16 range.
    
    Args:
        audio: Audio tensor (typically in range [-1, 1])
    
    Returns:
        Audio tensor in int16 range [-32768, 32767]
    """
    return torch.clamp(audio * 32767.0, -32768, 32767).to(torch.int16)


def int16_to_float32(audio: torch.Tensor) -> torch.Tensor:
    """
    Convert int16 audio to float32 [-1, 1] range.
    
    Args:
        audio: Audio tensor in int16 range
    
    Returns:
        Audio tensor in float32 range [-1, 1]
    """
    return audio.to(torch.float32) / 32768.0
