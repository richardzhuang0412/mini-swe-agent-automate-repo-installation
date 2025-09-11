# Qwen Code Context for mini_swe_agent Project

## Project Overview

This directory contains the `mini-swe-agent` project, a lightweight AI software engineering agent that can solve GitHub issues and perform various development tasks. The project is designed to be minimal (around 100 lines of core code) yet powerful, with a focus on simplicity and ease of deployment.

### Core Components

1. **mini-swe-agent**: The main AI agent implementation that can solve GitHub issues through bash commands
2. **github_repo_scraper**: A utility for scraping GitHub repositories based on various criteria
3. **Configuration files**: YAML configurations for different agent behaviors
4. **Examples**: Language-specific installation examples

## Project Structure

```
/home/ubuntu/mini_swe_agent/
├── mini-swe-agent/                 # Main agent implementation
│   ├── src/minisweagent/          # Source code
│   │   ├── agents/                # Agent implementations
│   │   ├── config/                # Configuration files
│   │   ├── environments/          # Execution environments
│   │   ├── models/                # Language model interfaces
│   │   ├── run/                   # Entry points
│   │   └── utils/                 # Utility functions
│   ├── tests/                     # Test suite
│   ├── docs/                      # Documentation
│   ├── pyproject.toml             # Project configuration
│   └── README.md                  # Main documentation
├── github_repo_scraper/           # GitHub repository scraper utility
│   ├── github_repo_scraper.py     # Main scraper script
│   ├── README_scraper.md          # Scraper documentation
│   └── requirements.txt           # Dependencies
├── examples/                      # Example scripts
│   └── language_specific_installation.py
├── config/                        # Installation configuration
│   └── installation_config.yaml
├── CLAUDE.md                      # Claude-specific documentation
└── README_INTEGRATION.md          # Integration documentation
```

## mini-swe-agent Core Implementation

### Key Files

- `src/minisweagent/agents/default.py`: The main 100-line agent implementation
- `src/minisweagent/models/litellm_model.py`: Language model interface using LiteLLM
- `src/minisweagent/environments/local.py`: Local execution environment
- `src/minisweagent/environments/docker.py`: Docker execution environment
- `src/minisweagent/run/mini.py`: Main entry point
- `src/minisweagent/config/mini.yaml`: Default configuration

### Architecture

The agent follows a simple control flow:
1. Initialize with a language model and execution environment
2. Run in a loop: query the model → parse action → execute action → observe result
3. Continue until task completion or limits reached

Key features:
- **Minimal**: Only ~100 lines of core logic
- **Bash-only**: Uses only bash commands, no special tools
- **Linear history**: Simple message history management
- **Subprocess execution**: Each command runs in isolation

## Using Python Bindings for Automated Repo Installation

For your specific use case of automated repository installation, here's how to use the Python bindings:

### Basic Setup

```python
from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model
from minisweagent.environments.docker import DockerEnvironment

# Create the agent with Docker environment for isolation
agent = DefaultAgent(
    get_model(model_name="claude-sonnet-4-20250514"),
    DockerEnvironment(image="python:3.11"),
)

# Run the installation task
task = "Clone the repository https://github.com/user/repo and install all dependencies. Then run the test suite and verify all tests pass."
exit_status, result = agent.run(task)
```

### Using OpenAI Models (GPT-4o-mini, GPT-4, etc.)

mini-swe-agent uses LiteLLM which supports multiple model providers including OpenAI. Here's how to use OpenAI models:

```python
from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model
from minisweagent.environments.docker import DockerEnvironment

# Using OpenAI GPT-4o-mini
agent = DefaultAgent(
    get_model(model_name="gpt-4o-mini"),
    DockerEnvironment(image="python:3.11"),
)

# Or set via environment variable
import os
os.environ["MSWEA_MODEL_NAME"] = "gpt-4o-mini"
agent = DefaultAgent(
    get_model(),
    DockerEnvironment(image="python:3.11"),
)
```

Make sure to set your OpenAI API key:
```bash
export OPENAI_API_KEY=your_openai_api_key_here
```

### Docker Environment Configuration

The Docker environment is ideal for repo installation tasks as it provides isolation:

```python
from minisweagent.environments.docker import DockerEnvironment

# Basic Docker environment
env = DockerEnvironment(image="python:3.11")

# Advanced configuration with custom settings
env = DockerEnvironment(
    image="python:3.11",
    cwd="/workspace",  # Working directory
    env={"DEBIAN_FRONTEND": "noninteractive"},  # Environment variables
    timeout=300,  # 5-minute timeout per command
    container_timeout="2h"  # 2-hour container lifetime
)
```

### Model Configuration

```python
from minisweagent.models import get_model

# Automatic model selection
model = get_model(model_name="gpt-4o")

# With custom configuration
model = get_model(model_name="gpt-4o-mini", config={
    "model_kwargs": {
        "temperature": 0.0,
        "max_tokens": 2000
    }
})
```

### Complete Example for Repo Installation

```python
from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model
from minisweagent.environments.docker import DockerEnvironment

def install_repo_agent(repo_url, base_image="python:3.11"):
    """Create an agent to install and test a repository."""
    
    # Configure the agent
    agent = DefaultAgent(
        get_model(model_name="gpt-4o-mini"),
        DockerEnvironment(
            image=base_image,
            cwd="/workspace",
            env={
                "DEBIAN_FRONTEND": "noninteractive",
                "PIP_PROGRESS_BAR": "off"
            },
            timeout=300  # 5 minutes per command
        ),
        # Custom configuration for repo installation
        system_template="""You are an expert software engineer tasked with installing and testing repositories.
        
        Your response must contain exactly ONE bash code block with ONE command.
        Include a THOUGHT section before your command explaining your reasoning.
        
        Focus on:
        1. Cloning the repository
        2. Identifying the project type (Python, Node.js, etc.)
        3. Installing dependencies
        4. Running the test suite
        5. Verifying tests pass""",
        
        instance_template=f"""Clone the repository {repo_url} and install it with all dependencies.
        Then run the test suite and verify all tests pass.
        
        Steps:
        1. Clone the repository
        2. Analyze the project structure to identify how to install dependencies
        3. Install all required dependencies
        4. Find and run the test suite
        5. Report the test results
        6. When complete, run: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
        
        Provide detailed output about what commands you're running and their results.""",
        
        cost_limit=5.0,  # Maximum cost limit
        step_limit=50    # Maximum steps
    )
    
    return agent

# Usage
repo_url = "https://github.com/user/repo"
agent = install_repo_agent(repo_url)
exit_status, result = agent.run(f"Install and test repository: {repo_url}")

# Access the full conversation history
messages = agent.messages
```

### Custom Agent for Repo Installation

For more control, you can create a specialized agent:

```python
from minisweagent.agents.default import DefaultAgent, AgentConfig
from dataclasses import dataclass

@dataclass
class RepoInstallConfig(AgentConfig):
    system_template: str = """You are an expert DevOps engineer specializing in repository installation and testing.
    
    Your task is to clone, install, and test repositories successfully.
    
    Response format:
    THOUGHT: Explain your reasoning
    ```bash
    single_command_here
    ```"""
    
    instance_template: str = """Install and test this repository: {{task}}
    
    Workflow:
    1. Clone repository
    2. Identify project type and dependencies
    3. Install dependencies
    4. Run tests
    5. Report results
    6. Run 'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT' when done"""
    
    step_limit: int = 100
    cost_limit: float = 10.0

class RepoInstallAgent(DefaultAgent):
    def __init__(self, model, env, **kwargs):
        super().__init__(model, env, config_class=RepoInstallConfig, **kwargs)
```

### Using Environment Factory (Recommended Approach)

The SWE-bench implementation shows a better approach using environment factories:

```python
from minisweagent.models import get_model
from minisweagent.environments import get_environment
from minisweagent.agents.default import DefaultAgent

# Using environment factory (more flexible)
env_config = {
    "environment_class": "docker",
    "image": "python:3.11",
    "cwd": "/workspace",
    "timeout": 300
}

env = get_environment(env_config)
model = get_model(model_name="gpt-4o-mini")

agent = DefaultAgent(model, env)
```

### Saving Results and Trajectories

```python
from minisweagent.run.utils.save import save_traj
from pathlib import Path

# After running the agent
exit_status, result = agent.run("Install repository...")

# Save the complete trajectory
save_traj(
    agent,
    Path("repo_installation_result.traj.json"),
    exit_status=exit_status,
    result=result,
    extra_info={"repo_url": "https://github.com/user/repo"}
)
```

## Example Scripts for Automated Installation

This directory includes example scripts that demonstrate how to use mini-swe-agent for automated repository installation:

### Basic Example (`repo_installer_example.py`)

A simple script for installing Python repositories:

```bash
python repo_installer_example.py https://github.com/psf/requests
```

### Advanced Example (`advanced_repo_installer.py`)

A more sophisticated script that handles multiple programming languages:

```bash
python advanced_repo_installer.py https://github.com/psf/requests python
python advanced_repo_installer.py https://github.com/expressjs/express javascript
```

### ECharts Demo (`demo_echarts_installer.py`)

A specific demo for installing the apache/echarts JavaScript repository using GPT-4o-mini:

```bash
python demo_echarts_installer.py
```

### Test Script (`test_mini_swe_agent.py`)

A script to verify that mini-swe-agent is working correctly:

```bash
python test_mini_swe_agent.py
```

See `README_REPO_INSTALLER.md` for detailed usage instructions.

## GitHub Repository Scraper

A Python utility for scraping GitHub repositories based on:
- Programming language
- Star count
- Activity metrics
- Creation/push dates

### Usage

```bash
# Search Python repositories with 100+ stars
python github_repo_scraper.py --language python --min-stars 100

# Search JavaScript repositories with date filtering
python github_repo_scraper.py --language javascript --created-after 2023-01-01

# Save results in multiple formats
python github_repo_scraper.py --language rust --format both --output rust_repos
```

## Development Workflow

### Building and Testing

```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
pytest

# Run tests with coverage
pytest --cov=minisweagent

# Linting
ruff check .

# Format code
ruff format .
```

### Configuration

The agent uses YAML configuration files located in `src/minisweagent/config/`:
- `mini.yaml`: Default configuration for the `mini` command
- `github_issue.yaml`: Configuration for GitHub issue solving
- Custom configurations can be specified with the `-c` flag

### Key Concepts

1. **Agents**: Implement the control flow logic
2. **Models**: Interface with language models (LiteLLM-based)
3. **Environments**: Execution contexts (local, docker, etc.)
4. **Templates**: Jinja2 templates for system/user messages

## Common Tasks

### Running the Agent

```bash
# Interactive mode
mini

# With specific task
mini --task "Create a Python script that reverses a string"

# With visual interface
mini -v

# With specific model
mini --model gpt-4o-mini
```

### Customization

1. **Configuration**: Modify YAML files in `config/` directory
2. **Prompts**: Adjust templates in configuration files
3. **Models**: Add new model implementations in `models/`
4. **Environments**: Create new environment classes in `environments/`

## Development Conventions

- Python 3.10+ required
- Follow Ruff linting rules (configured in `pyproject.toml`)
- Use type hints extensively
- Write tests for new functionality
- Keep the core logic minimal and focused
- Document public APIs

## Useful Environment Variables

- `GITHUB_TOKEN`: GitHub API token for higher rate limits
- `MSWEA_MINI_CONFIG_PATH`: Path to custom configuration file
- `MSWEA_GLOBAL_CONFIG_DIR`: Directory for global configuration
- `LITELLM_MODEL_REGISTRY_PATH`: Path to LiteLLM model registry
- `MSWEA_MODEL_NAME`: Default model name
- `MSWEA_MODEL_API_KEY`: API key for the model
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key

## Testing

The project uses pytest for testing with the following markers:
- `slow`: For tests that take longer to run

Run tests with:
```bash
# Run all tests
pytest

# Run fast tests only
pytest -k "not slow"

# Run tests in parallel
pytest -n auto
```