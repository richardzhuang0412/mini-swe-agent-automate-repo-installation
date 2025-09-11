#!/usr/bin/env python3
"""
GitHub Repository to Dockerfile Generator

Takes a GitHub repo name (e.g., 'expressjs/express'), clones it locally,
uses mini-swe-agent to figure out installation and testing steps,
then generates a Dockerfile with all the required steps.

Usage:
    python repo_to_dockerfile.py <github_repo> [--model MODEL_NAME] [--workspace DIR]

Example:
    python repo_to_dockerfile.py expressjs/express --model gpt-4o-mini
    python repo_to_dockerfile.py psf/requests --model claude-sonnet-4-20250514
"""

import sys
import json
import shutil
import subprocess
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any

# Add mini-swe-agent to Python path
sys.path.insert(0, str(Path(__file__).parent / "mini-swe-agent" / "src"))

from minisweagent.agents.default import DefaultAgent, AgentConfig
from minisweagent.environments.local import LocalEnvironment, LocalEnvironmentConfig
from minisweagent.models import get_model

@dataclass
class CommandTrackingConfig(LocalEnvironmentConfig):
    """Enhanced local environment config for tracking commands."""
    cwd: str = ""
    timeout: int = 300  # 5 minutes for complex builds
    env: Dict[str, str] = field(default_factory=lambda: {
        "DEBIAN_FRONTEND": "noninteractive",
        "PIP_PROGRESS_BAR": "off",
        "PYTHONUNBUFFERED": "1",
        "NPM_CONFIG_PROGRESS": "false",
        "NODE_ENV": "development"
    })

class CommandTrackingEnvironment(LocalEnvironment):
    """Environment that tracks all successful commands for Dockerfile generation."""
    
    def __init__(self, **kwargs):
        super().__init__(config_class=CommandTrackingConfig, **kwargs)
        self.successful_commands = []
        self.failed_commands = []
        
    def execute(self, command: str, cwd: str = "") -> Dict[str, Any]:
        """Execute command and track success/failure."""
        result = super().execute(command, cwd)
        
        # Track the command with its result
        command_info = {
            "command": command,
            "cwd": cwd or self.config.cwd,
            "returncode": result["returncode"],
            "output": result["output"]
        }
        
        if result["returncode"] == 0:
            self.successful_commands.append(command_info)
        else:
            self.failed_commands.append(command_info)
            
        return result
    
    def get_installation_commands(self) -> List[str]:
        """Extract commands that are likely installation/setup steps."""
        install_commands = []
        exploration_patterns = [
            "ls", "pwd", "cat", "head", "tail", "grep", "find", "which", "echo",
            "cd ", "mkdir -p", "rm -rf", "touch", "file", "stat", "wc", "sort"
        ]
        
        for cmd_info in self.successful_commands:
            command = cmd_info["command"].strip()
            
            # Skip empty commands
            if not command:
                continue
                
            # Skip exploration commands (but allow complex ones)
            is_exploration = any(
                command.startswith(pattern) or command == pattern 
                for pattern in exploration_patterns
            )
            
            # Include commands that install, build, or test
            is_install = any(keyword in command.lower() for keyword in [
                "install", "pip", "npm", "yarn", "apt-get", "apt", "yum", "brew",
                "cargo", "go mod", "mvn", "gradle", "composer", "bundle",
                "setup.py", "requirements", "package.json", "Makefile", "make",
                "cmake", "configure", "build", "compile", "test"
            ])
            
            if not is_exploration or is_install:
                install_commands.append(command)
                
        return install_commands

@dataclass
class DockerfileAgentConfig(AgentConfig):
    """Agent configuration focused on generating Dockerfile-compatible setup."""
    
    system_template: str = """You are a DevOps expert specializing in containerization and repository setup.

Your task is to analyze a repository and determine ALL the steps needed to:
1. Set up the environment (install system dependencies, language runtimes, etc.)
2. Install project dependencies 
3. Build the project (if needed)
4. Run the test suite successfully

IMPORTANT: You are working in a LOCAL environment, not Docker. The steps you discover will be used to generate a Dockerfile later.

Your response must contain exactly ONE bash command in triple backticks.
Include a THOUGHT section before your command explaining your reasoning.

Response format:
THOUGHT: Explain what you're trying to achieve and why

```bash
your_command_here
```

Focus on commands that would be needed to set up this project from scratch on a fresh system."""

    instance_template: str = """Repository Setup Analysis
======================

Repository: {{repo_name}}
Location: {{repo_path}}
Working Directory: {{repo_path}}

Your goal: Determine the complete setup process for this repository.

Please work through these steps systematically:

1. **EXPLORE**: Examine the repository structure to understand:
   - What programming language(s) are used
   - What dependency/package files exist (package.json, requirements.txt, etc.)
   - What build system is used
   - How tests are typically run

2. **SYSTEM SETUP**: Identify and install any system-level dependencies:
   - Programming language runtimes (Node.js, Python, Go, etc.)
   - System packages (build tools, libraries, etc.)
   - Package managers if not already available

3. **DEPENDENCY INSTALLATION**: Install project dependencies:
   - Use the appropriate package manager (npm, pip, cargo, etc.)
   - Follow any setup scripts or installation instructions
   - Handle any special requirements or configurations

4. **BUILD**: If the project needs building:
   - Run build commands (make, npm run build, cargo build, etc.)
   - Ensure all artifacts are created correctly

5. **TEST**: Locate and run the test suite:
   - Find test commands in package.json, Makefile, or documentation
   - Run tests and verify they pass
   - Try multiple test approaches if the first doesn't work

6. **FINALIZE**: When everything is working, output:
   echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT

Take your time and be thorough. The commands you run successfully will be used to generate a Dockerfile."""

    step_limit: int = 50
    cost_limit: float = 8.0

class DockerfileGeneratingAgent(DefaultAgent):
    """Agent that tracks commands to generate Dockerfile."""
    
    def __init__(self, model, env: CommandTrackingEnvironment, repo_name: str, repo_path: str, **kwargs):
        super().__init__(model, env, config_class=DockerfileAgentConfig, **kwargs)
        self.repo_name = repo_name
        self.repo_path = repo_path
        # Add template variables
        self.extra_template_vars.update({
            "repo_name": repo_name,
            "repo_path": repo_path
        })

def clone_repository(repo_name: str, workspace_dir: Path) -> Path:
    """Clone a GitHub repository locally."""
    # Parse repo name (e.g., 'expressjs/express' -> 'https://github.com/expressjs/express.git')
    if "/" not in repo_name:
        raise ValueError(f"Invalid repo name. Expected format: 'owner/repo', got: '{repo_name}'")
    
    repo_url = f"https://github.com/{repo_name}.git"
    repo_dir = workspace_dir / repo_name.split("/")[-1]  # e.g., 'express'
    
    print(f"Cloning {repo_url} to {repo_dir}...")
    
    # Remove existing directory if it exists
    if repo_dir.exists():
        print(f"Removing existing directory: {repo_dir}")
        shutil.rmtree(repo_dir)
    
    # Clone the repository
    result = subprocess.run(
        ["git", "clone", repo_url, str(repo_dir)],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone repository: {result.stderr}")
    
    print(f"Successfully cloned to {repo_dir}")
    return repo_dir

def detect_base_image_from_commands(commands: List[str]) -> str:
    """Analyze commands to determine appropriate Docker base image."""
    
    # Language/runtime indicators in commands
    language_indicators = {
        "python": ["pip", "python", "python3", "requirements.txt", "setup.py", "poetry", "pipenv"],
        "node": ["npm", "yarn", "node", "package.json", "typescript", "ts-node"],
        "go": ["go ", "go.mod", "go.sum"],
        "rust": ["cargo", "Cargo.toml", "rustc"],
        "java": ["mvn", "maven", "gradle", "java", "javac", ".jar"],
        "ruby": ["gem", "bundle", "ruby", "Gemfile"],
        "php": ["composer", "php"],
        "dotnet": ["dotnet", ".csproj", ".sln"],
    }
    
    detected_languages = []
    command_text = " ".join(commands).lower()
    
    for language, indicators in language_indicators.items():
        if any(indicator in command_text for indicator in indicators):
            detected_languages.append(language)
    
    # Choose base image based on detected language
    if "python" in detected_languages:
        return "python:3.11-slim"
    elif "node" in detected_languages:
        return "node:18-slim"
    elif "go" in detected_languages:
        return "golang:1.21-alpine"
    elif "rust" in detected_languages:
        return "rust:1.70-slim"
    elif "java" in detected_languages:
        return "openjdk:17-slim"
    elif "ruby" in detected_languages:
        return "ruby:3.2-slim"
    elif "php" in detected_languages:
        return "php:8.2-cli"
    elif "dotnet" in detected_languages:
        return "mcr.microsoft.com/dotnet/sdk:7.0"
    else:
        # Default to Ubuntu if we can't determine the language
        return "ubuntu:22.04"

def clean_command_for_docker(command: str, base_image: str) -> str:
    """Clean and adapt command for Docker environment."""
    # Remove sudo (not needed in containers)
    command = command.replace("sudo ", "")
    
    # Split compound commands and filter each part
    if "&&" in command:
        parts = [part.strip() for part in command.split("&&")]
        filtered_parts = []
        
        for part in parts:
            # Skip system updates if not needed
            if part.strip() in ["apt-get update", "apt update"]:
                continue
                
            # Skip language runtime installation if base image already has it
            should_skip = False
            if "node" in base_image:
                skip_patterns = ["apt-get install -y nodejs", "apt-get install nodejs", "apt install nodejs", 
                               "apt-get install -y npm", "apt-get install npm", "apt install npm"]
                if any(pattern in part for pattern in skip_patterns):
                    should_skip = True
            elif "python" in base_image:
                skip_patterns = ["apt-get install -y python", "apt-get install python", "apt install python",
                               "apt-get install -y python3", "apt-get install python3", "apt install python3"]
                if any(pattern in part for pattern in skip_patterns):
                    should_skip = True
            elif "golang" in base_image or "go:" in base_image:
                skip_patterns = ["apt-get install -y golang", "apt-get install golang", "apt install golang"]
                if any(pattern in part for pattern in skip_patterns):
                    should_skip = True
            
            if not should_skip and part.strip():
                filtered_parts.append(part)
        
        return " && ".join(filtered_parts) if filtered_parts else ""
    
    # Single command - check if should skip
    if "node" in base_image and any(pattern in command for pattern in ["apt-get install nodejs", "apt-get install npm", "apt install nodejs", "apt install npm"]):
        return ""
    elif "python" in base_image and any(pattern in command for pattern in ["apt-get install python", "apt install python"]):
        return ""
    elif ("golang" in base_image or "go:" in base_image) and "apt" in command and "golang" in command:
        return ""
    
    return command

def generate_dockerfile(commands: List[str], base_image: str, repo_name: str) -> str:
    """Generate Dockerfile content from successful commands."""
    
    dockerfile_lines = [
        f"# Generated Dockerfile for {repo_name}",
        f"# Base image determined from analysis: {base_image}",
        f"FROM {base_image}",
        "",
        "# Set working directory",
        "WORKDIR /app",
        "",
        "# Copy repository contents",
        "COPY . .",
        ""
    ]
    
    # Clean and categorize commands
    system_commands = []
    build_commands = []
    test_commands = []
    
    for cmd in commands:
        cleaned_cmd = clean_command_for_docker(cmd, base_image)
        if not cleaned_cmd:  # Skip empty commands
            continue
            
        cmd_lower = cleaned_cmd.lower()
        if any(keyword in cmd_lower for keyword in ["apt-get", "apt install", "yum install", "apk add"]):
            system_commands.append(cleaned_cmd)
        elif any(keyword in cmd_lower for keyword in ["test", "pytest", "npm test", "go test", "cargo test"]):
            test_commands.append(cleaned_cmd)
        else:
            build_commands.append(cleaned_cmd)
    
    # Add system package installation
    if system_commands:
        dockerfile_lines.extend([
            "# Install system dependencies",
            "RUN " + " && \\\n    ".join(system_commands),
            ""
        ])
    
    # Add build/setup commands
    if build_commands:
        dockerfile_lines.extend([
            "# Setup and build",
            "RUN " + " && \\\n    ".join(build_commands),
            ""
        ])
    
    # Add test verification (optional, as a separate RUN for debugging)
    if test_commands:
        dockerfile_lines.extend([
            "# Verify installation by running tests",
            "RUN " + " && \\\n    ".join(test_commands[:1]),  # Just run first test command
            ""
        ])
    
    # Add default command
    dockerfile_lines.extend([
        "# Default command",
        "CMD [\"/bin/bash\"]"
    ])
    
    return "\n".join(dockerfile_lines)

def save_results(repo_path: Path, commands: List[str], dockerfile_content: str, agent_messages: List[Dict]):
    """Save all results to agent-result directory."""
    result_dir = repo_path / "agent-result"
    result_dir.mkdir(exist_ok=True)
    
    # Save Dockerfile
    (result_dir / "Dockerfile").write_text(dockerfile_content)
    
    # Save extracted commands
    (result_dir / "commands_extracted.json").write_text(
        json.dumps(commands, indent=2)
    )
    
    # Save agent conversation log
    (result_dir / "agent_conversation.json").write_text(
        json.dumps(agent_messages, indent=2)
    )
    
    # Save human-readable summary
    summary = f"""# Repository Setup Summary

## Repository Analysis Results

**Commands extracted for Dockerfile:**
{chr(10).join(f"- {cmd}" for cmd in commands)}

## Generated Files:
- `Dockerfile` - Ready to build container
- `commands_extracted.json` - Raw command list
- `agent_conversation.json` - Full agent conversation
- `build_instructions.md` - This summary

## To test the generated Dockerfile:
```bash
cd {repo_path.name}
docker build -f agent-result/Dockerfile -t {repo_path.name.lower()}-test .
docker run --rm -it {repo_path.name.lower()}-test
```
"""
    (result_dir / "build_instructions.md").write_text(summary)
    
    print(f"\n✅ Results saved to {result_dir}/")
    print(f"   - Dockerfile")
    print(f"   - commands_extracted.json")
    print(f"   - agent_conversation.json") 
    print(f"   - build_instructions.md")

def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Generate Dockerfile from GitHub repository using mini-swe-agent"
    )
    parser.add_argument("repo", help="GitHub repository (format: owner/repo)")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model to use")
    parser.add_argument("--workspace", default="./workspace", help="Workspace directory")
    
    args = parser.parse_args()
    
    # Validate inputs
    if "/" not in args.repo:
        print("Error: Repository must be in format 'owner/repo'")
        sys.exit(1)
    
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(exist_ok=True)
    
    try:
        # Step 1: Clone repository
        repo_path = clone_repository(args.repo, workspace)
        
        # Step 2: Create command-tracking environment
        env = CommandTrackingEnvironment(cwd=str(repo_path))
        
        # Step 3: Create agent
        model = get_model(args.model, {
            "model_kwargs": {"temperature": 0.1, "max_tokens": 4000}
        })
        
        agent = DockerfileGeneratingAgent(
            model=model,
            env=env,
            repo_name=args.repo,
            repo_path=str(repo_path)
        )
        
        # Step 4: Run analysis
        print(f"\n🤖 Starting repository analysis with {args.model}...")
        task = "analyze_and_setup"
        exit_status, result = agent.run(task)
        
        print(f"\n📊 Analysis completed!")
        print(f"Exit status: {exit_status}")
        print(f"Model cost: ${agent.model.cost:.4f}")
        print(f"API calls: {agent.model.n_calls}")
        
        # Step 5: Extract installation commands
        install_commands = env.get_installation_commands()
        print(f"\n📝 Extracted {len(install_commands)} installation commands:")
        for i, cmd in enumerate(install_commands, 1):
            print(f"  {i}. {cmd}")
        
        if not install_commands:
            print("⚠️  No installation commands found. Agent may not have completed successfully.")
            print(f"Final result: {result}")
            return
        
        # Step 6: Generate Dockerfile
        base_image = detect_base_image_from_commands(install_commands)
        dockerfile_content = generate_dockerfile(install_commands, base_image, args.repo)
        
        print(f"\n🐳 Generated Dockerfile with base image: {base_image}")
        
        # Step 7: Save results
        save_results(repo_path, install_commands, dockerfile_content, agent.messages)
        
        print(f"\n✅ Complete! Generated Dockerfile for {args.repo}")
        print(f"📁 Repository location: {repo_path}")
        print(f"🐳 Dockerfile location: {repo_path}/agent-result/Dockerfile")
        
        if exit_status == "Submitted":
            print("🎉 Agent completed successfully!")
        else:
            print(f"⚠️  Agent finished with status: {exit_status}")
            print(f"Final message: {result}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()