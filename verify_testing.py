#!/usr/bin/env python3
"""
Test Output Parser for Mini-SWE-Agent Pipeline

This script parses test output from verify_dockerfile.py and produces parsed test status.
It connects the repo_to_dockerfile -> verify_dockerfile -> verify_testing pipeline.

Usage:
    python verify_testing.py path/to/directory --python-repo  # For Python repos
    python verify_testing.py path/to/Dockerfile               # For non-Python repos
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import parsers from existing log_parser
from log_parser.parsers.jest import parse_log_jest
from log_parser.parsers.mocha import parse_log_mocha
from log_parser.parsers.pytest import parse_log_pytest
from log_parser.parsers.go_test import parse_log_go_test
from log_parser.parsers.cargo import parse_log_cargo
from log_parser.parsers.maven import parse_log_maven


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


def load_repo_metadata(directory: Path) -> Optional[Dict]:
    """Load repo_metadata.json from directory."""
    metadata_path = directory / "repo_metadata.json"

    if not metadata_path.exists():
        print(f"Error: repo_metadata.json not found at {metadata_path}")
        return None

    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading repo_metadata.json: {e}")
        return None


def load_test_commands_legacy(directory: Path) -> Optional[Dict]:
    """Load legacy test_commands.json from directory (fallback)."""
    test_commands_path = directory / "test_commands.json"

    if not test_commands_path.exists():
        return None

    try:
        with open(test_commands_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Error reading legacy test_commands.json: {e}")
        return None


def load_test_output(directory: Path) -> Optional[str]:
    """Load test_output.txt from directory."""
    test_output_path = directory / "test_output.txt"

    if not test_output_path.exists():
        print(f"Error: test_output.txt not found at {test_output_path}")
        print(f"Make sure you ran verify_dockerfile.py first to generate test output")
        return None

    try:
        with open(test_output_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except IOError as e:
        print(f"Error reading test_output.txt: {e}")
        return None


def try_parsers(log_content: str, parser_names: List[str]) -> Optional[Tuple[Dict[str, str], str]]:
    """Try multiple parsers and return the first one that produces results along with parser name."""
    for parser_name in parser_names:
        if parser_name not in PARSERS:
            continue

        parser_func = PARSERS[parser_name]
        try:
            result = parser_func(log_content)
            if result:  # Parser returned some results
                print(f"Successfully parsed with {parser_name} parser")
                return result, parser_name
        except Exception as e:
            print(f"Parser {parser_name} failed with error: {e}")
            continue

    return None


def save_parsed_result(result: Dict[str, str], parser_name: str, directory: Path) -> None:
    """Save parsed test results to parsed_test_status.json."""
    output_path = directory / "parsed_test_status.json"

    output_data = {
        "parser": parser_name,
        "parsed_test_status": result,
    }

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Saved parsed test results to: {output_path}")
    except IOError as e:
        print(f"Error saving parsed test results: {e}")


def parse_test_output(directory: Path, is_python_repo: bool = False) -> Optional[Tuple[Dict[str, str], str]]:
    """
    Main parsing function for both Python and non-Python repos.

    Args:
        directory: Directory containing repo_metadata.json, test_output.txt
        is_python_repo: Whether this is a Python repository

    Returns:
        Tuple of (Dictionary mapping test case names to status, parser_name)
    """
    print(f"🔍 Parsing test output in: {directory}")
    print(f"📊 Repository type: {'Python' if is_python_repo else 'Non-Python'}")

    # Step 1: Load metadata (try new format first, then legacy)
    metadata = load_repo_metadata(directory)
    if not metadata:
        # Try legacy format
        print("⚠️  repo_metadata.json not found, trying legacy test_commands.json...")
        metadata = load_test_commands_legacy(directory)
        if not metadata:
            print("❌ Neither repo_metadata.json nor test_commands.json found")
            return None
        print("✅ Using legacy test_commands.json format")
    else:
        print("✅ Using repo_metadata.json format")

    # Step 2: Load test output
    log_content = load_test_output(directory)
    if not log_content:
        return None

    # Step 3: Extract metadata fields (handle both new and legacy formats)
    if 'test_commands' in metadata:
        # New format (repo_metadata.json)
        test_framework = metadata.get('test_framework', '').lower()
        language = metadata.get('language', '').lower()
        test_commands = metadata.get('test_commands', [])
        install_commands = metadata.get('install_commands', [])

        print(f"📋 Metadata (new format):")
        print(f"   Test framework: {test_framework}")
        print(f"   Language: {language}")
        print(f"   Test commands: {test_commands}")
        print(f"   Install commands: {install_commands}")
    else:
        # Legacy format (test_commands.json)
        test_framework = metadata.get('test_framework', '').lower()
        language = metadata.get('language', '').lower()
        test_command = metadata.get('test_command', '')

        print(f"📋 Metadata (legacy format):")
        print(f"   Test framework: {test_framework}")
        print(f"   Language: {language}")
        print(f"   Test command: {test_command}")

    # Step 4: Override language detection for Python repos if needed
    if is_python_repo and language != 'python':
        print(f"🐍 Overriding language detection: {language} -> python (due to --python-repo flag)")
        language = 'python'

    # Step 5: Try parsers in priority order
    print(f"🧪 Starting parser selection...")

    # Priority 1: Try exact framework match
    if test_framework and test_framework in PARSERS:
        print(f"   Priority 1: Trying exact framework match: {test_framework}")
        parser_result = try_parsers(log_content, [test_framework])
        if parser_result:
            result, parser_name = parser_result
            print(f"✅ Successfully parsed with framework-specific parser: {parser_name}")
            return result, parser_name
        print(f"   Framework parser {test_framework} produced no results")

    # Priority 2: Try all parsers for the language
    if language in LANGUAGE_FRAMEWORKS:
        framework_list = LANGUAGE_FRAMEWORKS[language]
        # Remove the already-tried framework to avoid duplicate attempts
        framework_list = [f for f in framework_list if f != test_framework]

        if framework_list:
            print(f"   Priority 2: Trying language-based parsers for {language}: {framework_list}")
            parser_result = try_parsers(log_content, framework_list)
            if parser_result:
                result, parser_name = parser_result
                print(f"✅ Successfully parsed with language-based parser: {parser_name}")
                return result, parser_name
            print(f"   No language-based parsers for {language} produced results")

    # Priority 3: Try all parsers as fallback
    all_parsers = list(PARSERS.keys())
    tried_parsers = [test_framework] + LANGUAGE_FRAMEWORKS.get(language, [])
    untried_parsers = [p for p in all_parsers if p not in tried_parsers]

    if untried_parsers:
        print(f"   Priority 3: Trying remaining parsers as fallback: {untried_parsers}")
        parser_result = try_parsers(log_content, untried_parsers)
        if parser_result:
            result, parser_name = parser_result
            print(f"✅ Successfully parsed with fallback parser: {parser_name}")
            return result, parser_name
        print(f"   No fallback parsers produced results")

    # Priority 4: Report error if language not supported
    if language not in LANGUAGE_FRAMEWORKS:
        print(f"⚠️  Unsupported language '{language}'")
        print(f"   Supported languages: {list(LANGUAGE_FRAMEWORKS.keys())}")

    print("❌ No parser was able to extract test results from the log")
    return None


def main():
    """Command-line interface for verify_testing.py."""
    parser = argparse.ArgumentParser(
        description="Parse test output from verify_dockerfile.py and generate parsed_test_status.json"
    )
    parser.add_argument(
        "path",
        help="Path to Dockerfile (non-Python) or directory containing installation script (Python)"
    )
    parser.add_argument(
        "--python-repo",
        action="store_true",
        help="Treat as Python repository (looks for conda installation script results)"
    )

    args = parser.parse_args()

    input_path = Path(args.path).resolve()

    # Determine directory based on input
    if input_path.is_dir():
        directory = input_path
    elif input_path.is_file():
        directory = input_path.parent
    else:
        print(f"❌ Path not found: {input_path}")
        sys.exit(1)

    print(f"🚀 Starting test output parsing...")
    print(f"📂 Working directory: {directory}")

    # Parse test output
    parse_result = parse_test_output(directory, args.python_repo)

    if parse_result:
        result, parser_name = parse_result

        # Summary
        total = len(result)
        passed = sum(1 for status in result.values() if status == "PASSED")
        failed = sum(1 for status in result.values() if status == "FAILED")
        skipped = sum(1 for status in result.values() if status == "SKIPPED")

        print(f"\n📊 Parsing Summary:")
        print(f"   Parser used: {parser_name}")
        print(f"   Total tests: {total}")
        print(f"   Passed: {passed}")
        print(f"   Failed: {failed}")
        print(f"   Skipped: {skipped}")

        # Show sample test results
        if total > 0:
            print(f"\n🧪 Sample Test Results (first 5):")
            items = list(result.items())
            for i, (test_name, status) in enumerate(items[:5]):
                status_icon = "✅" if status == "PASSED" else "❌" if status == "FAILED" else "⏭️"
                print(f"   {status_icon} {test_name}: {status}")

            if total > 5:
                print(f"   ... and {total - 5} more tests")

        # Save parsed results
        save_parsed_result(result, parser_name, directory)

        print(f"\n🎉 Test parsing completed successfully!")

        # Exit with non-zero code if there were failures
        if failed > 0:
            print(f"⚠️  {failed} test(s) failed")
            sys.exit(1)
        else:
            print(f"✅ All tests passed!")
            sys.exit(0)
    else:
        print("\n❌ Failed to parse test results")
        print("🔧 Troubleshooting tips:")
        print("   1. Make sure verify_dockerfile.py was run first")
        print("   2. Check that test_output.txt exists and contains test results")
        print("   3. Verify that repo_metadata.json has the correct test_framework")
        print("   4. Try using the --python-repo flag for Python repositories")
        sys.exit(1)


if __name__ == "__main__":
    main()