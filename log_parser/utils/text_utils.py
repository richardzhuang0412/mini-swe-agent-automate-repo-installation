"""
Text processing utilities for log parsing.
"""

import re
import hashlib
from typing import List, Optional


def strip_ansi(text: str) -> str:
    """
    Strip ANSI escape sequences from text.
    
    This removes color codes, cursor movement, and other terminal formatting.
    """
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text - collapse multiple spaces/newlines"""
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    # Replace multiple newlines with single newline
    text = re.sub(r'\n+', '\n', text)
    return text.strip()


def extract_lines_with_pattern(text: str, pattern: str, max_lines: int = 100) -> List[str]:
    """Extract lines that match a regex pattern"""
    regex = re.compile(pattern, re.IGNORECASE)
    lines = text.split('\n')
    matches = []
    
    for line in lines:
        if regex.search(line) and len(matches) < max_lines:
            matches.append(line.strip())
    
    return matches


def create_stable_test_id(file_path: Optional[str], suite: Optional[str], test_name: str) -> str:
    """
    Create a stable test ID that can be used as a dictionary key.
    
    Uses file path, suite, and test name when available. Falls back to hash
    if names are too long or contain problematic characters.
    """
    parts = []
    
    if file_path:
        # Use relative path and normalize separators
        normalized_path = file_path.replace('\\', '/').lstrip('./')
        parts.append(normalized_path)
    
    if suite:
        parts.append(suite)
    
    parts.append(test_name)
    
    test_id = "::".join(parts)
    
    # If the ID is too long or has problematic characters, use a hash
    if len(test_id) > 200 or any(char in test_id for char in ['<', '>', '|', '?', '*']):
        # Keep the test name but hash the rest
        hash_input = "::".join(parts[:-1]) if len(parts) > 1 else ""
        if hash_input:
            hash_suffix = hashlib.md5(hash_input.encode()).hexdigest()[:8]
            return f"{hash_suffix}::{test_name}"
        else:
            return test_name
    
    return test_id


def parse_duration(duration_str: str) -> Optional[float]:
    """
    Parse duration string into seconds as float.
    
    Supports formats like:
    - "1.23s" -> 1.23
    - "123ms" -> 0.123
    - "1m 30s" -> 90.0
    - "1:30" -> 90.0
    """
    if not duration_str:
        return None
    
    duration_str = duration_str.strip().lower()
    
    # Try simple seconds format: "1.23s"
    match = re.match(r'^(\d+(?:\.\d+)?)s?$', duration_str)
    if match:
        return float(match.group(1))
    
    # Try milliseconds: "123ms"
    match = re.match(r'^(\d+(?:\.\d+)?)ms$', duration_str)
    if match:
        return float(match.group(1)) / 1000.0
    
    # Try minutes and seconds: "1m 30s" or "1:30"
    match = re.match(r'^(\d+)m\s*(\d+(?:\.\d+)?)s?$', duration_str)
    if match:
        minutes = int(match.group(1))
        seconds = float(match.group(2))
        return minutes * 60 + seconds
    
    match = re.match(r'^(\d+):(\d+(?:\.\d+)?)$', duration_str)
    if match:
        minutes = int(match.group(1))
        seconds = float(match.group(2))
        return minutes * 60 + seconds
    
    # Try just a number (assume seconds)
    match = re.match(r'^(\d+(?:\.\d+)?)$', duration_str)
    if match:
        return float(match.group(1))
    
    return None


def truncate_message(message: str, max_length: int = 500) -> str:
    """Truncate a message to a maximum length, preserving readability"""
    if not message or len(message) <= max_length:
        return message
    
    # Try to truncate at word boundary
    truncated = message[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # If we found a space reasonably close to the end
        truncated = truncated[:last_space]
    
    return truncated + "..."


def clean_test_output(output: str) -> str:
    """
    Clean test output for better parsing.
    
    - Strips ANSI codes
    - Normalizes whitespace
    - Removes empty lines at start/end
    """
    cleaned = strip_ansi(output)
    cleaned = normalize_whitespace(cleaned)
    
    # Remove empty lines at start and end, but preserve internal structure
    lines = cleaned.split('\n')
    
    # Remove leading empty lines
    while lines and not lines[0].strip():
        lines.pop(0)
    
    # Remove trailing empty lines  
    while lines and not lines[-1].strip():
        lines.pop()
    
    return '\n'.join(lines)


def extract_error_context(output: str, error_line: str, context_lines: int = 3) -> str:
    """
    Extract context around an error line from test output.
    
    Args:
        output: Full test output
        error_line: The specific error line to find context for
        context_lines: Number of lines before and after to include
        
    Returns:
        String with context around the error
    """
    lines = output.split('\n')
    error_index = -1
    
    # Find the error line
    for i, line in enumerate(lines):
        if error_line.strip() in line.strip():
            error_index = i
            break
    
    if error_index == -1:
        return error_line  # Couldn't find context, just return the error line
    
    start = max(0, error_index - context_lines)
    end = min(len(lines), error_index + context_lines + 1)
    
    context_lines_list = lines[start:end]
    
    # Mark the actual error line
    if 0 <= error_index - start < len(context_lines_list):
        context_lines_list[error_index - start] = f">>> {context_lines_list[error_index - start]}"
    
    return '\n'.join(context_lines_list)