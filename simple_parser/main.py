#!/usr/bin/env python3
"""
Simple test log parser main script.

Takes a Dockerfile path, finds test_output.txt in the same folder,
reads test_commands.json to determine parser selection, and returns
test case to status mapping.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from parsers.jest import parse_log_jest
from parsers.mocha import parse_log_mocha
from parsers.pytest import parse_log_pytest
from parsers.go_test import parse_log_go_test
from parsers.cargo import parse_log_cargo
from parsers.maven import parse_log_maven


# Parser registry
PARSERS = {
    'jest': parse_log_jest,
    'mocha': parse_log_mocha,
    'pytest': parse_log_pytest,
    'go_test': parse_log_go_test,
    'cargo': parse_log_cargo,
    'maven': parse_log_maven,
}

# Language to framework mappings
LANGUAGE_FRAMEWORKS = {
    'javascript': ['jest', 'mocha'],
    'python': ['pytest'],
    'go': ['go_test'],
    'rust': ['cargo'],
    'java': ['maven'],
}


def load_test_commands(dockerfile_dir: Path) -> Optional[Dict]:
    """Load test_commands.json from the same directory as Dockerfile."""
    test_commands_path = dockerfile_dir / "test_commands.json"
    
    if not test_commands_path.exists():
        print(f"Error: test_commands.json not found at {test_commands_path}")
        return None
    
    try:
        with open(test_commands_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading test_commands.json: {e}")
        return None


def load_test_output(dockerfile_dir: Path) -> Optional[str]:
    """Load test_output.txt from the same directory as Dockerfile."""
    test_output_path = dockerfile_dir / "test_output.txt"
    
    if not test_output_path.exists():
        print(f"Error: test_output.txt not found at {test_output_path}")
        return None
    
    try:
        with open(test_output_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except IOError as e:
        print(f"Error reading test_output.txt: {e}")
        return None


def try_parsers(log_content: str, parser_names: List[str]) -> Optional[Dict[str, str]]:
    """Try multiple parsers and return the first one that produces results."""
    for parser_name in parser_names:
        if parser_name not in PARSERS:
            continue
            
        parser_func = PARSERS[parser_name]
        try:
            result = parser_func(log_content)
            if result:  # Parser returned some results
                print(f"Successfully parsed with {parser_name} parser")
                return result
        except Exception as e:
            print(f"Parser {parser_name} failed with error: {e}")
            continue
    
    return None


def parse_test_log(dockerfile_path: str) -> Optional[Dict[str, str]]:
    """
    Main parsing function.
    
    Args:
        dockerfile_path: Path to the Dockerfile
        
    Returns:
        Dictionary mapping test case names to status (PASSED/FAILED/SKIPPED)
    """
    dockerfile_path = Path(dockerfile_path)
    
    if not dockerfile_path.exists():
        print(f"Error: Dockerfile not found at {dockerfile_path}")
        return None
        
    dockerfile_dir = dockerfile_path.parent
    
    # Load test configuration
    test_commands = load_test_commands(dockerfile_dir)
    if not test_commands:
        return None
        
    # Load test output
    log_content = load_test_output(dockerfile_dir)
    if not log_content:
        return None
    
    test_framework = test_commands.get('test_framework', '').lower()
    language = test_commands.get('language', '').lower()
    
    print(f"Test framework: {test_framework}")
    print(f"Language: {language}")
    
    # Priority 1: Try exact framework match
    if test_framework in PARSERS:
        print(f"Trying exact framework match: {test_framework}")
        result = try_parsers(log_content, [test_framework])
        if result:
            return result
        print(f"Framework parser {test_framework} produced no results")
    
    # Priority 2: Try all parsers for the language
    if language in LANGUAGE_FRAMEWORKS:
        framework_list = LANGUAGE_FRAMEWORKS[language]
        # Remove the already-tried framework to avoid duplicate attempts
        framework_list = [f for f in framework_list if f != test_framework]
        
        if framework_list:
            print(f"Trying language-based parsers for {language}: {framework_list}")
            result = try_parsers(log_content, framework_list)
            if result:
                return result
            print(f"No language-based parsers for {language} produced results")
    
    # Priority 3: Report error if language not found
    if language not in LANGUAGE_FRAMEWORKS:
        print(f"Error: Unsupported language '{language}'")
        print(f"Supported languages: {list(LANGUAGE_FRAMEWORKS.keys())}")
        return None
    
    print("No parser was able to extract test results from the log")
    return None


def main():
    """Command-line interface."""
    if len(sys.argv) != 2:
        print("Usage: python main.py <dockerfile_path>")
        print("Example: python main.py /path/to/agent-result/repo-name/Dockerfile")
        sys.exit(1)
    
    dockerfile_path = sys.argv[1]
    
    result = parse_test_log(dockerfile_path)
    
    if result:
        print("\n=== Test Results ===")
        for test_name, status in result.items():
            print(f"{test_name}: {status}")
        
        # Summary
        total = len(result)
        passed = sum(1 for status in result.values() if status == "PASSED")
        failed = sum(1 for status in result.values() if status == "FAILED") 
        skipped = sum(1 for status in result.values() if status == "SKIPPED")
        
        print(f"\n=== Summary ===")
        print(f"Total tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Skipped: {skipped}")
        
        # Exit with non-zero code if there were failures
        if failed > 0:
            sys.exit(1)
    else:
        print("Failed to parse test results")
        sys.exit(1)


if __name__ == "__main__":
    main()