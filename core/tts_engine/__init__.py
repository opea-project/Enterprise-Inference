"""
TTS Engine initialization.
"""

from .codec import SNACCodec
from .constants import AUDIO_TOKEN_OFFSETS, SAMPLE_RATE, BIT_DEPTH, CHANNELS

__all__ = [
    'SNACCodec',
    'AUDIO_TOKEN_OFFSETS',
    'SAMPLE_RATE',
    'BIT_DEPTH',
    'CHANNELS',
]
