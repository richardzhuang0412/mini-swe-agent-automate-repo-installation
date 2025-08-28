#!/usr/bin/env python3
"""
Example script demonstrating how to use mini-swe-agent for automated repository installation.

This script shows how to:
1. Create an agent with Docker environment for isolation
2. Run installation tasks
3. Save results and trajectories
"""

import sys
from pathlib import Path

# Add the mini-swe-agent to path
sys.path.insert(0, str(Path(__file__).parent / "mini-swe-agent" / "src"))

from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model
from minisweagent.environments.docker import DockerEnvironment
from minisweagent.run.utils.save import save_traj


def create_repo_installation_agent(repo_url, base_image="python:3.11", model_name="gpt-4o-mini"):
    """
    Create an agent configured for repository installation and testing.
    
    Args:
        repo_url (str): URL of the repository to install
        base_image (str): Base Docker image to use
        model_name (str): Name of the model to use
        
    Returns:
        DefaultAgent: Configured agent instance
    """
    # Create the agent with Docker environment for isolation
    agent = DefaultAgent(
        get_model(model_name, config={"model_name": model_name}),
        DockerEnvironment(
            image=base_image,
            cwd="/workspace",
            env={
                "DEBIAN_FRONTEND": "noninteractive",
                "PIP_PROGRESS_BAR": "off",
                "PYTHONUNBUFFERED": "1"
            },
            timeout=300,  # 5 minutes per command
            container_timeout="2h"  # 2 hour container lifetime
        ),
        # Custom configuration for repo installation
        system_template="""You are an expert DevOps engineer specializing in repository installation and testing.

Your response must contain exactly ONE bash code block with ONE command.
Include a THOUGHT section before your command explaining your reasoning.

Focus on:
1. Cloning the repository
2. Identifying the project type and dependencies
3. Installing dependencies correctly
4. Finding and running the test suite
5. Verifying tests pass

Response format:
THOUGHT: Explain your reasoning and what you plan to do
```bash
single_command_here
```""",
        
        instance_template=f"""Install and test this repository: {repo_url}

Workflow:
1. Clone the repository to /workspace
2. Analyze the project structure to identify how to install dependencies
3. Install all required dependencies
4. Find and run the test suite
5. Report the test results
6. When complete, run: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT

Provide detailed output about what commands you're running and their results.
If tests fail, try to understand why and suggest fixes."""
    )
    
    return agent


def main():
    """Main function demonstrating repo installation."""
    if len(sys.argv) < 2:
        print("Usage: python repo_installer_example.py <repo_url> [model_name]")
        print("Example: python repo_installer_example.py https://github.com/psf/requests")
        sys.exit(1)
    
    repo_url = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "gpt-4o-mini"
    
    print(f"Creating agent for repository: {repo_url}")
    print(f"Using model: {model_name}")
    
    # Create the agent
    agent = create_repo_installation_agent(repo_url, model_name=model_name)
    
    # Define the task
    task = f"Clone the repository {repo_url}, install all dependencies, and run the test suite. Report whether tests pass."
    
    try:
        print("Running installation task...")
        exit_status, result = agent.run(task)
        
        print(f"\nTask completed with exit status: {exit_status}")
        print(f"Result: {result}")
        
        # Save the trajectory
        output_file = Path(f"repo_install_{repo_url.split('/')[-1]}.traj.json")
        save_traj(
            agent,
            output_file,
            exit_status=exit_status,
            result=result,
            extra_info={
                "repo_url": repo_url,
                "model_name": model_name,
                "base_image": "python:3.11"
            }
        )
        print(f"Trajectory saved to: {output_file}")
        
    except Exception as e:
        print(f"Error during installation: {e}")
        import traceback
        traceback.print_exc()
        
        # Save error trajectory
        output_file = Path(f"repo_install_{repo_url.split('/')[-1]}_error.traj.json")
        save_traj(
            agent,
            output_file,
            exit_status=type(e).__name__,
            result=str(e),
            extra_info={
                "repo_url": repo_url,
                "model_name": model_name,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
        print(f"Error trajectory saved to: {output_file}")


if __name__ == "__main__":
    main()
