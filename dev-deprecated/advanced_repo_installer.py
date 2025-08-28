#!/usr/bin/env python3
"""
Advanced example script demonstrating how to use mini-swe-agent for automated repository installation
with language-specific handling.
"""

import sys
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any

# Add the mini-swe-agent to path
sys.path.insert(0, str(Path(__file__).parent / "mini-swe-agent" / "src"))

from minisweagent.agents.default import DefaultAgent, AgentConfig
from minisweagent.models import get_model
from minisweagent.environments.docker import DockerEnvironment
from minisweagent.run.utils.save import save_traj

# MODEL_NAME = "gpt-4o-mini"
MODEL_NAME = "claude-sonnet-4-20250514"

# Language-specific Docker images
LANGUAGE_IMAGES = {
    "python": "python:3.11",
    "javascript": "node:18",
    "typescript": "node:18",
    "go": "golang:1.21",
    "rust": "rust:1.70",
    "java": "openjdk:17",
    "ruby": "ruby:3.2",
    "php": "php:8.2",
}

# Language-specific environment variables
LANGUAGE_ENV_VARS = {
    "python": {
        "DEBIAN_FRONTEND": "noninteractive",
        "PIP_PROGRESS_BAR": "off",
        "PYTHONUNBUFFERED": "1"
    },
    "javascript": {
        "DEBIAN_FRONTEND": "noninteractive",
        "NODE_ENV": "development"
    },
    "go": {
        "DEBIAN_FRONTEND": "noninteractive",
        "GOPATH": "/go",
        "GOCACHE": "/tmp/go-build"
    },
    "rust": {
        "DEBIAN_FRONTEND": "noninteractive",
        "CARGO_HOME": "/cargo",
        "CARGO_TARGET_DIR": "/target"
    }
}

@dataclass
class RepoInstallConfig(AgentConfig):

    """Configuration for repository installation agent."""
    system_template: str = """You are an expert DevOps engineer specializing in repository installation and testing.
    
    You are working in a Docker environment with base image {{base_image}}.
    
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
    ```"""
    
    instance_template: str = """Install and test this {{language}} repository: {{repo_url}}
    
    Repository details:
    - URL: {{repo_url}}
    - Primary language: {{language}}
    - Base image: {{base_image}}
    
    Workflow:
    1. Clone the repository to /workspace
    2. Analyze the project structure to identify how to install dependencies
    3. Install all required dependencies using the appropriate package manager
    4. Find and run the test suite
    5. Report the test results
    6. When complete, run: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
    
    Language-specific guidance:
    {%- if language == "python" -%}
    - Look for requirements.txt, setup.py, pyproject.toml, or Pipfile
    - Use pip, poetry, or pipenv as appropriate
    - Run pytest, unittest, or tox for testing
    {%- elif language == "javascript" or language == "typescript" -%}
    - Look for package.json and package-lock.json or yarn.lock
    - Use npm or yarn as appropriate
    - Run npm test or yarn test
    {%- elif language == "go" -%}
    - Look for go.mod and go.sum
    - Use go mod download for dependencies
    - Run go test ./...
    {%- elif language == "rust" -%}
    - Look for Cargo.toml and Cargo.lock
    - Use cargo build for compilation
    - Run cargo test
    {%- elif language == "java" -%}
    - Look for pom.xml (Maven) or build.gradle (Gradle)
    - Use mvn or gradle as appropriate
    - Run mvn test or gradle test
    {%- endif -%}
    
    Provide detailed output about what commands you're running and their results.
    If tests fail, try to understand why and suggest fixes."""
    
    step_limit: int = 100
    cost_limit: float = 10.0


class RepoInstallAgent(DefaultAgent):
    """Specialized agent for repository installation."""
    
    def __init__(self, model, env, language: str = "python", repo_url: str = "", base_image: str = "", **kwargs):
        super().__init__(model, env, config_class=RepoInstallConfig, **kwargs)
        self.language = language
        # Set template variables
        self.extra_template_vars["language"] = language
        self.extra_template_vars["repo_url"] = repo_url
        self.extra_template_vars["base_image"] = base_image


def get_language_base_image(language: str) -> str:
    """Get the appropriate base Docker image for a language."""
    return LANGUAGE_IMAGES.get(language.lower(), "ubuntu:22.04")


def get_language_env_vars(language: str) -> Dict[str, str]:
    """Get language-specific environment variables."""
    return LANGUAGE_ENV_VARS.get(language.lower(), {
        "DEBIAN_FRONTEND": "noninteractive"
    })


def create_language_specific_agent(
    repo_url: str, 
    language: str = "python", 
    model_name: str = MODEL_NAME
) -> RepoInstallAgent:
    """
    Create an agent configured for language-specific repository installation.
    
    Args:
        repo_url (str): URL of the repository to install
        language (str): Primary programming language of the repository
        model_name (str): Name of the model to use
        
    Returns:
        RepoInstallAgent: Configured agent instance
    """
    base_image = get_language_base_image(language)
    env_vars = get_language_env_vars(language)
    
    # Create the agent with Docker environment for isolation
    agent = RepoInstallAgent(
        get_model(model_name, config={"model_name": model_name}),
        DockerEnvironment(
            image=base_image,
            cwd="/workspace",
            env=env_vars,
            timeout=600,  # 10 minutes per command for complex builds
            container_timeout="4h"  # 4 hour container lifetime
        ),
        language=language.lower(),
        repo_url=repo_url,
        base_image=base_image
    )
    
    return agent


def generate_installation_report(agent: RepoInstallAgent, exit_status: str, result: str, repo_url: str) -> Dict[str, Any]:
    """Generate a detailed installation report."""
    return {
        "repository": repo_url,
        "language": agent.language,
        "exit_status": exit_status,
        "result": result,
        "model_stats": {
            "api_calls": agent.model.n_calls,
            "total_cost": agent.model.cost
        },
        "conversation_length": len(agent.messages),
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }


def main():
    """Main function demonstrating language-specific repo installation."""
    if len(sys.argv) < 2:
        print("Usage: python advanced_repo_installer.py <repo_url> [language] [model_name]")
        print("Example: python advanced_repo_installer.py https://github.com/psf/requests python")
        sys.exit(1)
    
    repo_url = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "python"
    model_name = sys.argv[3] if len(sys.argv) > 3 else MODEL_NAME
    
    print(f"Creating agent for {language} repository: {repo_url}")
    print(f"Using model: {model_name}")
    print(f"Base image: {get_language_base_image(language)}")
    
    # Create the agent
    agent = create_language_specific_agent(repo_url, language, model_name)
    
    # Define the task
    task = f"Clone the {language} repository {repo_url}, install all dependencies, and run the test suite. Report whether tests pass."
    
    try:
        print("Running installation task...")
        exit_status, result = agent.run(task)
        
        print(f"\nTask completed with exit status: {exit_status}")
        print(f"Result: {result}")
        
        # Generate and save report
        report = generate_installation_report(agent, exit_status, result, repo_url)
        report_file = Path(f"repo_install_{repo_url.split('/')[-1]}_report.json")
        report_file.write_text(json.dumps(report, indent=2))
        print(f"Report saved to: {report_file}")
        
        # Save the trajectory
        output_file = Path(f"repo_install_{repo_url.split('/')[-1]}.traj.json")
        save_traj(
            agent,
            output_file,
            exit_status=exit_status,
            result=result,
            extra_info={
                "repo_url": repo_url,
                "language": language,
                "model_name": model_name,
                "base_image": get_language_base_image(language),
                "report": report
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
                "language": language,
                "model_name": model_name,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
        print(f"Error trajectory saved to: {output_file}")


if __name__ == "__main__":
    main()
