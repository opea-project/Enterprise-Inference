"""
Helper function to clean internal monologue from LLM responses
"""
import re


def clean_internal_monologue(text: str) -> str:
    """
    Remove internal thinking/monologue from LLM response.
    
    Handles removal of:
    1. <think>...</think> tags (typical of Qwen/Reasoning models)
    2. Internal monologue patterns at the start of the response
    
    Args:
        text (str): Raw LLM response text.
        
    Returns:
        str: Cleaned text with internal monologue removed.
    """
    if not text:
        return text
    
    # Step 1: Remove <think>...</think> blocks (Qwen's internal thinking)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Step 2: Remove any remaining thinking patterns at the start
    paragraphs = text.split('\n\n')
    
    if len(paragraphs) <= 1:
        return text.strip()
    
    # Patterns that indicate internal thinking (case-insensitive)
    thinking_indicators = [
        r'\bokay,?\s+let\'?s\b',
        r'\bfirst,?\s+i\b',
        r'\bi\s+need\s+to\b',
        r'\bi\s+should\b',
        r'\bstarting\s+with\b',
        r'\bputting\s+(this|it)\s+together\b',
        r'\bthe\s+user\s+(wants|is\s+asking)\b',
        r'\blooking\s+at\b',
        r'\bgoing\s+through\b',
    ]
    
    # Find first paragraph that's NOT thinking
    cleaned_paragraphs = []
    found_content = False
    
    for para in paragraphs:
        para_stripped = para.strip()
        if not para_stripped:
            continue
            
        para_lower = para_stripped.lower()
        
        # Check if this is thinking
        has_thinking = any(re.search(pattern, para_lower, re.IGNORECASE) for pattern in thinking_indicators)
        
        if not has_thinking or found_content:
            cleaned_paragraphs.append(para)
            found_content = True
    
    # If we filtered everything, return original (safety)
    if not cleaned_paragraphs:
        return text.strip()
    
    return '\n\n'.join(cleaned_paragraphs).strip()