# Automated Repository Installation with mini-swe-agent

This directory contains examples demonstrating how to use mini-swe-agent for automated repository installation and testing.

## Overview

The goal is to create an AI agent that can:
1. Clone a repository
2. Install all dependencies
3. Run the test suite
4. Verify that tests pass
5. Generate a Docker image with the installed repository

## Files

- `repo_installer_example.py` - Basic example for Python repositories
- `advanced_repo_installer.py` - Advanced example with language-specific handling
- `demo_echarts_installer.py` - Specific demo for apache/echarts using GPT-4o-mini
- `test_mini_swe_agent.py` - Test script to verify functionality
- `gpt4o_mini_config.yaml` - Configuration file for GPT-4o-mini
- `set_gpt4o_mini.sh` - Script to set GPT-4o-mini as default model

## Prerequisites

1. Install mini-swe-agent dependencies:
   ```bash
   cd mini-swe-agent
   pip install -e .
   ```

2. Set up your model API key (for OpenAI, Anthropic, etc.):
   ```bash
   # For OpenAI
   export OPENAI_API_KEY=your_api_key_here
   
   # For Anthropic
   export ANTHROPIC_API_KEY=your_api_key_here
   ```

## Usage

### Basic Example

```bash
python repo_installer_example.py https://github.com/psf/requests
```

### Advanced Example (with language specification)

```bash
python advanced_repo_installer.py https://github.com/psf/requests python
python advanced_repo_installer.py https://github.com/expressjs/express javascript
python advanced_repo_installer.py https://github.com/golang/example go
```

### ECharts Demo (using GPT-4o-mini)

```bash
python demo_echarts_installer.py
```

### Testing the Setup

```bash
python test_mini_swe_agent.py
```

## Setting GPT-4o-mini as Default Model

There are several ways to use GPT-4o-mini as your default model:

### 1. Environment Variable (Recommended)

```bash
export MSWEA_MODEL_NAME="gpt-4o-mini"
python demo_echarts_installer.py
```

Or use the provided script:
```bash
source set_gpt4o_mini.sh
python demo_echarts_installer.py
```

### 2. Configuration File

Use the provided `gpt4o_mini_config.yaml`:
```bash
cd mini-swe-agent
python -m minisweagent.run.mini -c ../gpt4o_mini_config.yaml
```

### 3. Command Line Flag

```bash
python demo_echarts_installer.py gpt-4o-mini
```

## How It Works

1. **Agent Creation**: Creates a mini-swe-agent instance with a Docker environment for isolation
2. **Task Assignment**: Provides the agent with instructions to install and test a repository
3. **Execution**: The agent runs in a loop, executing bash commands to:
   - Clone the repository
   - Identify project type and dependencies
   - Install dependencies
   - Run tests
   - Report results
4. **Results**: Saves the conversation trajectory and generates reports

## Language Support

The advanced installer supports multiple languages with appropriate base images:

- Python: `python:3.11`
- JavaScript/TypeScript: `node:18`
- Go: `golang:1.21`
- Rust: `rust:1.70`
- Java: `openjdk:17`
- Ruby: `ruby:3.2`
- PHP: `php:8.2`

## Output Files

Each run generates:
- `repo_install_<name>.traj.json` - Complete conversation trajectory
- `repo_install_<name>_report.json` - Installation summary report
- `repo_install_<name>_error.traj.json` - Error trajectory (if failed)

## Customization

You can customize the agent behavior by modifying:
- System prompts in the template configurations
- Environment variables and Docker settings
- Cost and step limits
- Base Docker images for different languages