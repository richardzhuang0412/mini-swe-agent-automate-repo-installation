#!/usr/bin/env python3
"""
Simplified script to generate Dockerfiles from GitHub repositories using mini-swe-agent.

This version lets the agent handle everything directly - no command tracking or post-processing.
The agent creates the Dockerfile using git clone approach with extended timeouts.
"""

import sys
import os
import shutil
import yaml
import platform
import subprocess
import argparse
import json
import re
from pathlib import Path
from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Dict

from minisweagent.agents.default import DefaultAgent
from minisweagent.models.litellm_model import LitellmModel
from minisweagent.run.utils.save import save_traj

@dataclass
class ExtendedLocalEnvironmentConfig:
    """Extended LocalEnvironmentConfig with increased timeout for long-running operations."""
    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)
    timeout: int = 300  # 5 minutes instead of 30 seconds


class ExtendedLocalEnvironment:
    """Extended LocalEnvironment with longer timeout for complex repository operations."""
    
    def __init__(self, *, config_class: type = ExtendedLocalEnvironmentConfig, **kwargs):
        """This class executes bash commands directly on the local machine with extended timeouts."""
        self.config = config_class(**kwargs)

    def execute(self, command: str, cwd: str = ""):
        """Execute a command in the local environment and return the result as a dict."""
        cwd = cwd or self.config.cwd or os.getcwd()
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            cwd=cwd,
            env=os.environ | self.config.env,
            timeout=self.config.timeout,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return {"output": result.stdout, "returncode": result.returncode}

    def get_template_vars(self) -> dict[str, Any]:
        return asdict(self.config) | platform.uname()._asdict() | os.environ


def extract_test_command_from_dockerfile(dockerfile_path: Path) -> Optional[Dict]:
    """
    Extract test command information from a Dockerfile by parsing RUN commands.
    This is a fallback in case the agent didn't create test_commands.json.
    """
    if not dockerfile_path.exists():
        return None
    
    dockerfile_content = dockerfile_path.read_text()
    
    # Look for RUN commands that likely run tests
    test_patterns = [
        r'RUN\s+(npm\s+test)',
        r'RUN\s+(yarn\s+test)',
        r'RUN\s+(pytest)',
        r'RUN\s+(python\s+-m\s+pytest)',
        r'RUN\s+(cargo\s+test)', 
        r'RUN\s+(go\s+test)',
        r'RUN\s+(mvn\s+test)',
        r'RUN\s+(gradle\s+test)',
        r'RUN\s+(.+test.+)',  # Generic fallback
    ]
    
    for pattern in test_patterns:
        match = re.search(pattern, dockerfile_content, re.IGNORECASE)
        if match:
            test_command = match.group(1)
            
            # Try to determine framework from command - standardized names
            framework = "unknown"
            language = "unknown"
            
            if "npm" in test_command or "yarn" in test_command:
                # Try to detect specific JS framework
                framework = "mocha"  # Default, could be jest
                language = "javascript"
            elif "pytest" in test_command:
                framework = "pytest"
                language = "python"
            elif "cargo test" in test_command:
                framework = "cargo"
                language = "rust"
            elif "go test" in test_command:
                framework = "go_test"
                language = "go"
            elif "mvn" in test_command:
                framework = "maven"
                language = "java"
            elif "gradle" in test_command:
                framework = "maven"  # Use maven parser for gradle too
                language = "java"
            
            return {
                "test_command": test_command,
                "test_framework": framework,
                "language": language
            }
    
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Generate a Dockerfile for a GitHub repository using mini-swe-agent."
    )
    parser.add_argument(
        "repo_name",
        type=str,
        help="GitHub repository in the form owner/repo (e.g., expressjs/express)",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default="claude-sonnet-4-20250514",
        help="Model name to use (default: claude-sonnet-4-20250514)",
    )
    args = parser.parse_args()

    repo_name = args.repo_name
    MODEL_NAME = args.model_name

    print(f"🚀 Generating Dockerfile for {repo_name} using model '{MODEL_NAME}'...")

    # Create repo-specific directory in agent-result/ under current working directory
    base_result_dir = Path("agent-result")
    base_result_dir.mkdir(exist_ok=True)
    
    # Create folder with repo name (replace / with -)
    repo_folder_name = repo_name.replace("/", "-")
    repo_result_dir = base_result_dir / repo_folder_name
    
    if repo_result_dir.exists():
        shutil.rmtree(repo_result_dir)
    repo_result_dir.mkdir()
    
    print(f"📁 Results will be saved to: {repo_result_dir}")
    
    # Setup model
    model = LitellmModel(model_name=MODEL_NAME)
    
    # Setup environment with extended timeout
    environment = ExtendedLocalEnvironment()
    
    # Load dockerfile generation config
    config_path = Path(__file__).parent / "dockerfile_generation.yaml"
    config_data = yaml.safe_load(config_path.read_text())["agent"]
    
    agent = DefaultAgent(
        model,
        environment,
        **config_data
    )
    
    try:
        # Run the agent - it will handle everything including Dockerfile creation
        print(f"🤖 Starting agent to analyze {repo_name}...")
        
        exit_status, result = agent.run(task=repo_name, dockerfile_path=f"agent-result/{repo_folder_name}/Dockerfile")
        
        # Save trajectory
        trajectory_path = repo_result_dir / "trajectory.json"
        print(f"💾 Saving agent trajectory to: {trajectory_path}")
        save_traj(agent, trajectory_path, exit_status=exit_status, result=result)
        
        # Check if Dockerfile was created
        dockerfile_path = repo_result_dir / "Dockerfile"
        test_commands_path = repo_result_dir / "test_commands.json"
        
        if dockerfile_path.exists():
            print(f"✅ Dockerfile successfully created at {dockerfile_path}")
            print("\n📋 Generated Dockerfile:")
            print("-" * 50)
            print(dockerfile_path.read_text())
            print("-" * 50)
            
            # Check for test commands file
            if test_commands_path.exists():
                print(f"✅ Test commands file created at {test_commands_path}")
                print("\n🧪 Test Commands Configuration:")
                print("-" * 50)
                print(test_commands_path.read_text())
                print("-" * 50)
            else:
                print("⚠️  Warning: test_commands.json was not created by agent")
                # Try to extract from Dockerfile as fallback
                extracted_commands = extract_test_command_from_dockerfile(dockerfile_path)
                if extracted_commands:
                    print("📋 Attempting to extract test commands from Dockerfile...")
                    with open(test_commands_path, 'w') as f:
                        json.dump(extracted_commands, f, indent=2)
                    print(f"✅ Created test_commands.json from Dockerfile analysis")
                    print("\n🧪 Extracted Test Commands Configuration:")
                    print("-" * 50)
                    print(json.dumps(extracted_commands, indent=2))
                    print("-" * 50)
                else:
                    print("❌ Could not extract test commands from Dockerfile")
            
            print("🎉 Dockerfile generation completed successfully!")
        else:
            print("❌ No Dockerfile was created. Check the agent output above.")
            print(f"Exit status: {exit_status}, Result: {result}")
            
    except Exception as e:
        print(f"❌ Error running agent: {e}")
        
        # Still try to save trajectory if possible
        try:
            trajectory_path = repo_result_dir / "trajectory_error.json"
            save_traj(agent, trajectory_path, exit_status="ERROR", result=str(e))
        except:
            pass
        raise


if __name__ == "__main__":
    main()