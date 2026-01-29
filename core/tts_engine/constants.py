"""
Token constants for Svara TTS model. 
Centralizes all token IDs and special tokens used throughout the codebase.

NOTE:
- BOS_TOKEN is once at the beginning of the whole prompt.
- Text block (human side) is wrapped with START_OF_HUMAN, AUDIO_TOKEN, ..., END_OF_HUMAN
- Audio reference block (AI side) is wrapped with START_OF_AI, START_OF_SPEECH, ..., END_OF_SPEECH, END_OF_AI
- For final generation step, end prompt with: START_OF_AI, START_OF_SPEECH
- END_OF_TURN comes after each complete human/AI block
"""

# ============================================================================
# Base Tokenizer Configuration
# ============================================================================

TOKENISER_LENGTH = 128256  # Base vocabulary size of the llama3.2 tokenizer

# ============================================================================
# Special Tokens (from tokenizer)
# ============================================================================

### BEGIN OF TEXT ###
BOS_TOKEN     = 128000 # <|begin_of_text|> | bos
BOS_TOKEN_STR = "<|begin_of_text|>"

### END OF TEXT ###
END_OF_TEXT     = 128001 # <|end_of_text|> | eos
END_OF_TEXT_STR = "<|end_of_text|>"

### END OF TURN ###
END_OF_TURN     = 128009 # <|eot_id|> | eot
END_OF_TURN_STR = "<|eot_id|>"

### AUDIO TOKEN ###
AUDIO_TOKEN     = 156939 # <|audio|> | audio
AUDIO_TOKEN_STR = "<|audio|>"

### Special Speech Tokens ###
START_OF_SPEECH = 128257 # <custom_token_1>
START_OF_SPEECH_STR = "<custom_token_1>"

END_OF_SPEECH   = 128258 # <custom_token_2>
END_OF_SPEECH_STR = "<custom_token_2>"

START_OF_HUMAN  = 128259 # <custom_token_3>
START_OF_HUMAN_STR = "<custom_token_3>"

END_OF_HUMAN    = 128260 # <custom_token_4>
END_OF_HUMAN_STR = "<custom_token_4>"

START_OF_AI     = 128261 # <custom_token_5>
START_OF_AI_STR = "<custom_token_5>"

END_OF_AI       = 128262 # <custom_token_6>
END_OF_AI_STR = "<custom_token_6>"

PAD_TOKEN       = 128263 # <custom_token_7>
PAD_TOKEN_STR = "<custom_token_7>"

# ============================================================================
# Audio Token Configuration
# ============================================================================

AUDIO_TOKENS_START = TOKENISER_LENGTH + 10  # 128266
AUDIO_VOCAB_SIZE   = 4096  # Each hierarchical level has 4096 possible codes

# Audio token offset positions (7 tokens per frame)
# These are added to raw SNAC codes [0, 4096] to map them into model vocabulary
AUDIO_TOKEN_OFFSETS = [
    AUDIO_TOKENS_START + (0 * AUDIO_VOCAB_SIZE),  # 128266 - codes[0]
    AUDIO_TOKENS_START + (1 * AUDIO_VOCAB_SIZE),  # 132362 - codes[1][2*i]
    AUDIO_TOKENS_START + (2 * AUDIO_VOCAB_SIZE),  # 136458 - codes[2][4*i]
    AUDIO_TOKENS_START + (3 * AUDIO_VOCAB_SIZE),  # 140554 - codes[2][4*i+1]
    AUDIO_TOKENS_START + (4 * AUDIO_VOCAB_SIZE),  # 144650 - codes[1][2*i+1]
    AUDIO_TOKENS_START + (5 * AUDIO_VOCAB_SIZE),  # 148746 - codes[2][4*i+2]
    AUDIO_TOKENS_START + (6 * AUDIO_VOCAB_SIZE),  # 152842 - codes[2][4*i+3]
]

# ============================================================================
# Audio Codec Configuration
# ============================================================================

SAMPLE_RATE = 24000  # SNAC model operates at 24kHz
BIT_DEPTH = 16       # PCM16 output
CHANNELS = 1         # Mono audio
