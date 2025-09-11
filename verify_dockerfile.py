#!/usr/bin/env python3
"""
Dockerfile Verification Tool

Tests generated Dockerfiles to ensure they build and run correctly.
This is a companion tool to repo_to_dockerfile.py
"""

import sys
import subprocess
import argparse
import json
from pathlib import Path
from typing import Tuple, Optional
import threading
import time

def run_command(cmd: list, cwd: Optional[Path] = None, timeout: int = 300) -> Tuple[int, str]:
    """Run a command and return exit code and output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, f"Error running command: {e}"

def run_command_with_progress(cmd: list, cwd: Optional[Path] = None, timeout: int = 300) -> Tuple[int, str]:
    """Run a command with real-time output streaming."""
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        output_lines = []
        
        # Read output line by line and print in real-time
        while True:
            line = process.stdout.readline()
            if not line:
                break
            print(line.rstrip())  # Print without extra newline
            output_lines.append(line)
            sys.stdout.flush()  # Ensure immediate output
        
        # Wait for process to complete
        process.wait(timeout=timeout)
        
        return process.returncode, ''.join(output_lines)
        
    except subprocess.TimeoutExpired:
        process.kill()
        return -1, f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, f"Error running command: {e}"

def verify_dockerfile(dockerfile_path: Path, image_name: str = None, show_progress: bool = True) -> bool:
    """Verify that a Dockerfile builds successfully."""
    
    if not dockerfile_path.exists():
        print(f"❌ Dockerfile not found: {dockerfile_path}")
        return False
    
    if not image_name:
        # Use the directory name where the Dockerfile is located
        image_name = f"{dockerfile_path.parent.name.lower()}-test"
    
    print(f"🔍 Verifying Dockerfile: {dockerfile_path}")
    print(f"🏷️  Image name: {image_name}")
    
    # Step 1: Build the Docker image
    print("\n1️⃣  Building Docker image...")
    
    build_cmd = [
        "docker", "build", 
        "-f", str(dockerfile_path),
        "-t", image_name,
        str(dockerfile_path.parent)  # Use the directory containing the Dockerfile as build context
    ]
    
    if show_progress:
        print("📦 Build progress (real-time):")
        print("=" * 50)
        exit_code, output = run_command_with_progress(build_cmd, timeout=600)  # 10 minute timeout for build
        print("=" * 50)
    else:
        exit_code, output = run_command(build_cmd, timeout=600)  # 10 minute timeout for build
    
    if exit_code == 0:
        print("✅ Docker build successful!")
    else:
        print("❌ Docker build failed!")
        if not show_progress:
            print("Build output:")
            print(output)
        return False
    
    # Step 2: Test running the container
    print("\n2️⃣  Testing container execution...")
    run_cmd = [
        "docker", "run", "--rm", 
        image_name, 
        "echo", "Container is working"
    ]
    
    exit_code, output = run_command(run_cmd, timeout=60)
    
    if exit_code == 0:
        print("✅ Container runs successfully!")
        print(f"Output: {output.strip()}")
    else:
        print("❌ Container failed to run!")
        print(f"Output: {output}")
        return False
    
    # Step 3: Check if we can run basic commands
    print("\n3️⃣  Testing basic commands in container...")
    basic_tests = [
        ["ls", "/app"],  # Check working directory
        ["pwd"],         # Check current directory
    ]
    
    for test_cmd in basic_tests:
        docker_cmd = ["docker", "run", "--rm", image_name] + test_cmd
        exit_code, output = run_command(docker_cmd, timeout=30)
        
        if exit_code == 0:
            print(f"✅ Command '{' '.join(test_cmd)}' successful")
        else:
            print(f"⚠️  Command '{' '.join(test_cmd)}' failed (this may be expected)")
    
    # Step 4: Run tests and collect output
    print("\n4️⃣  Running tests and collecting output...")
    test_success = run_tests_and_collect_output(dockerfile_path, image_name)
    
    print(f"\n🎉 Dockerfile verification completed successfully!")
    print(f"🐳 Image '{image_name}' is ready to use")
    
    return True

def run_tests_and_collect_output(dockerfile_path: Path, image_name: str) -> bool:
    """Run tests from test_commands.json and save output to test_output.txt."""
    dockerfile_dir = dockerfile_path.parent
    test_commands_path = dockerfile_dir / "test_commands.json"
    test_output_path = dockerfile_dir / "test_output.txt"
    
    # Check if test_commands.json exists
    if not test_commands_path.exists():
        print(f"⚠️  No test_commands.json found at {test_commands_path}")
        print("   Skipping test output collection")
        return True
    
    try:
        # Load test configuration
        with open(test_commands_path, 'r') as f:
            test_config = json.load(f)
        
        test_command = test_config.get('test_command', '')
        test_framework = test_config.get('test_framework', '')
        language = test_config.get('language', '')
        
        if not test_command:
            print("⚠️  No test_command found in test_commands.json")
            print("   Skipping test output collection")
            return True
            
        print(f"🧪 Found test configuration:")
        print(f"   Command: {test_command}")
        print(f"   Framework: {test_framework}")
        print(f"   Language: {language}")
        
        # Run the test command in the Docker container
        print(f"🔄 Running test command in container...")
        
        # Split the command into parts for Docker execution
        test_cmd_parts = test_command.split()
        docker_cmd = ["docker", "run", "--rm", image_name] + test_cmd_parts
        
        print(f"   Executing: {' '.join(docker_cmd)}")
        
        # Run with extended timeout for tests
        exit_code, output = run_command(docker_cmd, timeout=600)  # 10 minutes
        
        # Save the output regardless of success/failure
        print(f"💾 Saving test output to {test_output_path}")
        with open(test_output_path, 'w', encoding='utf-8') as f:
            f.write(output)
        
        if exit_code == 0:
            print("✅ Tests completed successfully")
        else:
            print(f"⚠️  Tests completed with exit code {exit_code}")
            print("   (This may be expected if there are test failures)")
        
        print(f"📊 Test output captured ({len(output)} characters)")
        
        # Show a preview of the output
        lines = output.split('\n')
        preview_lines = lines[:5] + (['...'] if len(lines) > 10 else []) + lines[-5:]
        print("📋 Test output preview:")
        for line in preview_lines:
            print(f"   {line}")
            
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing test_commands.json: {e}")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def cleanup_image(image_name: str) -> None:
    """Remove the test Docker image."""
    print(f"\n🧹 Cleaning up image: {image_name}")
    cleanup_cmd = ["docker", "rmi", image_name]
    exit_code, output = run_command(cleanup_cmd, timeout=60)
    
    if exit_code == 0:
        print("✅ Image removed successfully")
    else:
        print("⚠️  Could not remove image (it may not exist)")

def main():
    """Main CLI interface for Dockerfile verification."""
    parser = argparse.ArgumentParser(
        description="Verify generated Dockerfiles build and run correctly, and collect test output"
    )
    parser.add_argument("dockerfile_path", help="Path to Dockerfile")
    parser.add_argument("--image-name", help="Docker image name for testing")
    parser.add_argument("--cleanup", action="store_true", help="Remove test image after verification")
    parser.add_argument("--no-progress", action="store_true", help="Disable real-time progress output")
    
    args = parser.parse_args()
    
    dockerfile_path = Path(args.dockerfile_path).resolve()
    if not dockerfile_path.exists():
        print(f"❌ Dockerfile not found: {dockerfile_path}")
        sys.exit(1)
    
    # Generate image name if not provided
    image_name = args.image_name or f"{dockerfile_path.parent.name.lower()}-verification-test"
    
    try:
        # Check if Docker is available
        exit_code, output = run_command(["docker", "--version"], timeout=10)
        if exit_code != 0:
            print("❌ Docker is not available or not running")
            print("Please ensure Docker is installed and the daemon is running")
            sys.exit(1)
        
        print(f"🐳 Using Docker: {output.strip()}")
        
        # Verify the Dockerfile
        show_progress = not args.no_progress
        success = verify_dockerfile(dockerfile_path, image_name, show_progress)
        
        if success:
            print(f"\n🎉 Verification successful! Your Dockerfile works correctly.")
            
            # Show usage instructions
            print(f"\n📋 Usage instructions:")
            print(f"   docker run --rm -it {image_name}")
            print(f"   docker run --rm {image_name} <your-command-here>")
            
            if args.cleanup:
                cleanup_image(image_name)
                
            sys.exit(0)
        else:
            print(f"\n❌ Verification failed. Check the Dockerfile and try again.")
            if args.cleanup:
                cleanup_image(image_name)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n⏹️  Verification interrupted by user")
        if args.cleanup:
            cleanup_image(image_name)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        if args.cleanup:
            cleanup_image(image_name)
        sys.exit(1)

if __name__ == "__main__":
    main()