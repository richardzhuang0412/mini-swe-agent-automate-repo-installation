#!/usr/bin/env python3
"""
Test script for the Dockerfile generator.

This script tests the basic functionality without requiring API keys
by using mock data and testing individual components.
"""

import json
from pathlib import Path
import tempfile
import shutil

# Import the functions we want to test
import sys
sys.path.insert(0, str(Path(__file__).parent))

from repo_to_dockerfile import (
    detect_base_image_from_commands,
    generate_dockerfile,
    save_results
)

def test_base_image_detection():
    """Test base image detection from different command patterns."""
    print("🧪 Testing base image detection...")
    
    test_cases = [
        (["pip install requests", "python setup.py test"], "python:3.11-slim"),
        (["npm install", "npm test", "node server.js"], "node:18-slim"),
        (["go mod download", "go test ./..."], "golang:1.21-alpine"),
        (["cargo build", "cargo test"], "rust:1.70-slim"),
        (["mvn clean install", "java -jar app.jar"], "openjdk:17-slim"),
        (["bundle install", "ruby test.rb"], "ruby:3.2-slim"),
        (["composer install", "php test.php"], "php:8.2-cli"),
        (["apt-get update", "make"], "ubuntu:22.04"),  # Unknown language
    ]
    
    for commands, expected_image in test_cases:
        detected = detect_base_image_from_commands(commands)
        status = "✅" if detected == expected_image else "❌"
        print(f"  {status} Commands: {commands[:20]}... -> {detected}")
        if detected != expected_image:
            print(f"      Expected: {expected_image}, Got: {detected}")
    
    print()

def test_dockerfile_generation():
    """Test Dockerfile generation with sample commands."""
    print("🧪 Testing Dockerfile generation...")
    
    sample_commands = [
        "apt-get update && apt-get install -y git",
        "pip install --upgrade pip",
        "pip install -r requirements.txt", 
        "python setup.py install",
        "pytest tests/"
    ]
    
    base_image = "python:3.11-slim"
    repo_name = "test/repo"
    
    dockerfile = generate_dockerfile(sample_commands, base_image, repo_name)
    
    print("Generated Dockerfile:")
    print("-" * 50)
    print(dockerfile)
    print("-" * 50)
    
    # Basic validation
    assert "FROM python:3.11-slim" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "COPY . ." in dockerfile
    assert "RUN" in dockerfile
    
    print("✅ Dockerfile generation test passed!")
    print()

def test_save_results():
    """Test saving results to agent-result directory."""
    print("🧪 Testing result saving...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir) / "test-repo"
        repo_path.mkdir()
        
        sample_commands = ["pip install requests", "python -m pytest"]
        sample_dockerfile = "FROM python:3.11\nWORKDIR /app\nCOPY . .\nRUN pip install requests"
        sample_messages = [{"role": "user", "content": "test message"}]
        
        # Test the save function
        save_results(repo_path, sample_commands, sample_dockerfile, sample_messages)
        
        # Check that files were created
        result_dir = repo_path / "agent-result"
        expected_files = [
            "Dockerfile",
            "commands_extracted.json", 
            "agent_conversation.json",
            "build_instructions.md"
        ]
        
        for filename in expected_files:
            filepath = result_dir / filename
            if filepath.exists():
                print(f"  ✅ Created {filename}")
            else:
                print(f"  ❌ Missing {filename}")
        
        # Validate content
        dockerfile_content = (result_dir / "Dockerfile").read_text()
        assert "FROM python:3.11" in dockerfile_content
        
        commands_content = json.loads((result_dir / "commands_extracted.json").read_text())
        assert commands_content == sample_commands
        
    print("✅ Save results test passed!")
    print()

def test_command_filtering():
    """Test the command filtering logic."""
    print("🧪 Testing command filtering...")
    
    # Mock the CommandTrackingEnvironment behavior
    all_commands = [
        {"command": "ls -la", "returncode": 0, "output": "file listing"},
        {"command": "cat README.md", "returncode": 0, "output": "readme content"},
        {"command": "pip install -r requirements.txt", "returncode": 0, "output": "installing..."},
        {"command": "python setup.py test", "returncode": 0, "output": "test output"},
        {"command": "echo 'hello'", "returncode": 0, "output": "hello"},
        {"command": "npm install", "returncode": 0, "output": "installing npm deps..."},
        {"command": "pwd", "returncode": 0, "output": "/workspace"},
    ]
    
    # Simulate the filtering logic
    exploration_patterns = [
        "ls", "pwd", "cat", "head", "tail", "grep", "find", "which", "echo",
        "cd ", "mkdir -p", "rm -rf", "touch", "file", "stat", "wc", "sort"
    ]
    
    filtered_commands = []
    for cmd_info in all_commands:
        command = cmd_info["command"].strip()
        
        # Skip exploration commands unless they contain install keywords
        is_exploration = any(
            command.startswith(pattern) or command == pattern 
            for pattern in exploration_patterns
        )
        
        is_install = any(keyword in command.lower() for keyword in [
            "install", "pip", "npm", "yarn", "apt-get", "setup.py", "test"
        ])
        
        if not is_exploration or is_install:
            filtered_commands.append(command)
    
    expected_filtered = [
        "pip install -r requirements.txt",
        "python setup.py test", 
        "npm install"
    ]
    
    print(f"  Original commands: {len(all_commands)}")
    print(f"  Filtered commands: {len(filtered_commands)}")
    print(f"  Expected: {expected_filtered}")
    print(f"  Actual: {filtered_commands}")
    
    if filtered_commands == expected_filtered:
        print("  ✅ Command filtering works correctly")
    else:
        print("  ❌ Command filtering needs adjustment")
    
    print()

def run_all_tests():
    """Run all component tests."""
    print("🚀 Running Dockerfile Generator Tests")
    print("=" * 50)
    
    test_base_image_detection()
    test_dockerfile_generation()
    test_save_results()
    test_command_filtering()
    
    print("🎉 All tests completed!")
    print("\n📋 To test with a real repository:")
    print("   1. Set your API key: export OPENAI_API_KEY='your-key'")
    print("   2. Run: python repo_to_dockerfile.py expressjs/express --model gpt-4o-mini")
    print("   3. Verify: python verify_dockerfile.py workspace/express --cleanup")

if __name__ == "__main__":
    run_all_tests()