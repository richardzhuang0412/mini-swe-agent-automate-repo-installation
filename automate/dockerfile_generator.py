#!/usr/bin/env python3
"""
Demo script for generating Dockerfile instructions for repository installation and testing.
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


@dataclass
class DockerfileGeneratorConfig(AgentConfig):
    """Configuration for Dockerfile generation agent."""
    system_template: str = """You are an expert DevOps engineer specializing in creating Dockerfiles and installation instructions.
    
    Your task is to analyze a repository, understand how to install it, and create a complete Dockerfile with instructions.
    
    Your response must contain exactly ONE bash code block with ONE command.
    Include a THOUGHT section before your command explaining your reasoning.
    
    Focus on:
    1. Cloning the repository
    2. Identifying the project type and dependencies
    3. Creating a Dockerfile that can build and test the project
    4. Providing clear instructions for using the Dockerfile
    
    Response format:
    THOUGHT: Explain your reasoning and what you plan to do
    ```bash
    single_command_here
    ```"""
    
    instance_template: str = """Create a Dockerfile and installation instructions for this {{language}} repository: {{repo_url}}
    
    Repository details:
    - URL: {{repo_url}}
    - Primary language: {{language}}
    - Base image: {{base_image}}
    
    Your task is to:
    1. Clone and analyze the repository
    2. Understand the project structure and dependencies
    3. Create a Dockerfile that can:
       - Install all dependencies
       - Build the project (if needed)
       - Run the test suite
    4. Provide clear instructions on how to use the Dockerfile
    5. Output the complete Dockerfile content and instructions to a file
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
    {%- endif -%}
    
    Final deliverable should include:
    1. A complete Dockerfile
    2. Clear instructions on how to build and run it
    3. Commands to run the test suite
    4. Any important notes about the installation process
    
    Save everything to a file named 'dockerfile_instructions.md' and then run the completion command."""
    
    step_limit: int = 100
    cost_limit: float = 10.0


class DockerfileGeneratorAgent(DefaultAgent):
    """Specialized agent for generating Dockerfiles and instructions."""
    
    def __init__(self, model, env, language: str = "python", repo_url: str = "", base_image: str = "", **kwargs):
        super().__init__(model, env, config_class=DockerfileGeneratorConfig, **kwargs)
        self.language = language
        # Set template variables
        self.extra_template_vars["language"] = language
        self.extra_template_vars["repo_url"] = repo_url
        self.extra_template_vars["base_image"] = base_image


def create_dockerfile_generator(
    repo_url: str, 
    language: str = "python", 
    model_name: str = "gpt-4o-mini"
) -> DockerfileGeneratorAgent:
    """
    Create an agent configured for generating Dockerfiles and instructions.
    
    Args:
        repo_url (str): URL of the repository
        language (str): Primary programming language of the repository
        model_name (str): Name of the model to use
        
    Returns:
        DockerfileGeneratorAgent: Configured agent instance
    """
    # Language-specific Docker images
    LANGUAGE_IMAGES = {
        "python": "python:3.11",
        "javascript": "node:18",
        "typescript": "node:18",
        "go": "golang:1.21",
        "rust": "rust:1.70",
        "java": "openjdk:17",
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
    
    base_image = LANGUAGE_IMAGES.get(language.lower(), "ubuntu:22.04")
    env_vars = LANGUAGE_ENV_VARS.get(language.lower(), {
        "DEBIAN_FRONTEND": "noninteractive"
    })
    
    # Create the agent with Docker environment for isolation
    agent = DockerfileGeneratorAgent(
        get_model(model_name, config={"model_name": model_name}),
        DockerEnvironment(
            image=base_image,
            cwd="/workspace",
            env=env_vars,
            timeout=600,  # 10 minutes per command
            container_timeout="4h"  # 4 hour container lifetime
        ),
        language=language.lower(),
        repo_url=repo_url,
        base_image=base_image
    )
    
    return agent


def generate_report(agent: DockerfileGeneratorAgent, exit_status: str, result: str, repo_url: str) -> Dict[str, Any]:
    """Generate a detailed report."""
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
    """Main function to generate Dockerfile and instructions."""
    if len(sys.argv) < 2:
        print("Usage: python dockerfile_generator.py <repo_url> [language] [model_name]")
        print("Example: python dockerfile_generator.py https://github.com/expressjs/express javascript")
        sys.exit(1)
    
    repo_url = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "javascript"
    model_name = sys.argv[3] if len(sys.argv) > 3 else "gpt-4o-mini"
    
    print(f"Creating Dockerfile generator for {language} repository: {repo_url}")
    print(f"Using model: {model_name}")
    
    # Create the agent
    agent = create_dockerfile_generator(repo_url, language, model_name)
    
    # Define the task
    task = f"Create a Dockerfile and installation instructions for the {language} repository {repo_url}. Save the complete Dockerfile and instructions to a file named 'dockerfile_instructions.md'."
    
    try:
        print("Generating Dockerfile and instructions...")
        exit_status, result = agent.run(task)
        
        print(f"\nTask completed with exit status: {exit_status}")
        print(f"Result: {result}")
        
        # Try to extract the Dockerfile content from the container
        try:
            # Get the Dockerfile content from the container
            output = agent.env.execute("cat dockerfile_instructions.md")
            if output.get("output"):
                dockerfile_content = output["output"]
                dockerfile_file = Path(f"dockerfile_instructions_{repo_url.split('/')[-1]}.md")
                dockerfile_file.write_text(dockerfile_content)
                print(f"Dockerfile instructions saved to: {dockerfile_file}")
        except Exception as e:
            print(f"Could not extract Dockerfile: {e}")
        
        # Generate and save report
        report = generate_report(agent, exit_status, result, repo_url)
        report_file = Path(f"dockerfile_generation_{repo_url.split('/')[-1]}_report.json")
        report_file.write_text(json.dumps(report, indent=2))
        print(f"Report saved to: {report_file}")
        
        # Save the trajectory
        output_file = Path(f"dockerfile_generation_{repo_url.split('/')[-1]}.traj.json")
        save_traj(
            agent,
            output_file,
            exit_status=exit_status,
            result=result,
            extra_info={
                "repo_url": repo_url,
                "language": language,
                "model_name": model_name,
                "report": report
            }
        )
        print(f"Trajectory saved to: {output_file}")
        
    except Exception as e:
        print(f"Error during Dockerfile generation: {e}")
        import traceback
        traceback.print_exc()
        
        # Save error trajectory
        output_file = Path(f"dockerfile_generation_{repo_url.split('/')[-1]}_error.traj.json")
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