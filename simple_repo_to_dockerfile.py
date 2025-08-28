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
from pathlib import Path
from dataclasses import asdict, dataclass, field
from typing import Any

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

def main():
    if len(sys.argv) != 2:
        print("Usage: python simple_repo_to_dockerfile.py <github_repo>")
        print("Example: python simple_repo_to_dockerfile.py expressjs/express")
        sys.exit(1)
    
    repo_name = sys.argv[1]
    print(f"🚀 Generating Dockerfile for {repo_name}...")
    
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
    model = LitellmModel(model_name="claude-3-5-sonnet-20241022")
    
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
        if dockerfile_path.exists():
            print(f"✅ Dockerfile successfully created at {dockerfile_path}")
            print("\n📋 Generated Dockerfile:")
            print("-" * 50)
            print(dockerfile_path.read_text())
            print("-" * 50)
            
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