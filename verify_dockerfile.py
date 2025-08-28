#!/usr/bin/env python3
"""
Dockerfile Verification Tool

Tests generated Dockerfiles to ensure they build and run correctly.
This is a companion tool to repo_to_dockerfile.py
"""

import sys
import subprocess
import argparse
from pathlib import Path
from typing import Tuple, Optional

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

def verify_dockerfile(dockerfile_path: Path, repo_path: Path, image_name: str = None) -> bool:
    """Verify that a Dockerfile builds successfully."""
    
    if not dockerfile_path.exists():
        print(f"❌ Dockerfile not found: {dockerfile_path}")
        return False
    
    if not image_name:
        image_name = f"{repo_path.name.lower()}-test"
    
    print(f"🔍 Verifying Dockerfile: {dockerfile_path}")
    print(f"📁 Repository path: {repo_path}")
    print(f"🏷️  Image name: {image_name}")
    
    # Step 1: Build the Docker image
    print("\n1️⃣  Building Docker image...")
    build_cmd = [
        "docker", "build", 
        "-f", str(dockerfile_path),
        "-t", image_name,
        str(repo_path)
    ]
    
    exit_code, output = run_command(build_cmd, timeout=600)  # 10 minute timeout for build
    
    if exit_code == 0:
        print("✅ Docker build successful!")
    else:
        print("❌ Docker build failed!")
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
    
    print(f"\n🎉 Dockerfile verification completed successfully!")
    print(f"🐳 Image '{image_name}' is ready to use")
    
    return True

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
        description="Verify generated Dockerfiles build and run correctly"
    )
    parser.add_argument("repo_path", help="Path to repository directory")
    parser.add_argument("--dockerfile", help="Path to Dockerfile (default: repo/agent-result/Dockerfile)")
    parser.add_argument("--image-name", help="Docker image name for testing")
    parser.add_argument("--cleanup", action="store_true", help="Remove test image after verification")
    
    args = parser.parse_args()
    
    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        print(f"❌ Repository path not found: {repo_path}")
        sys.exit(1)
    
    # Determine Dockerfile path
    if args.dockerfile:
        dockerfile_path = Path(args.dockerfile).resolve()
    else:
        dockerfile_path = repo_path / "agent-result" / "Dockerfile"
    
    # Generate image name if not provided
    image_name = args.image_name or f"{repo_path.name.lower()}-verification-test"
    
    try:
        # Check if Docker is available
        exit_code, output = run_command(["docker", "--version"], timeout=10)
        if exit_code != 0:
            print("❌ Docker is not available or not running")
            print("Please ensure Docker is installed and the daemon is running")
            sys.exit(1)
        
        print(f"🐳 Using Docker: {output.strip()}")
        
        # Verify the Dockerfile
        success = verify_dockerfile(dockerfile_path, repo_path, image_name)
        
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