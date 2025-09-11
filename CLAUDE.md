# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository implements an automated pipeline that converts GitHub repositories into execution environments through Dockerfiles. It uses mini-swe-agent to analyze repositories, determine installation and testing procedures, then generates Dockerfiles that reproduce the complete setup process.

## Core Components

### Main Scripts

- **`repo_to_dockerfile.py`** - Main pipeline script that uses command tracking to extract installation steps
- **`simple_repo_to_dockerfile.py`** - Simplified version that lets the agent handle everything directly
- **`verify_dockerfile.py`** - Verification tool that tests generated Dockerfiles
- **`dockerfile_generation.yaml`** - Agent configuration for Dockerfile generation

### Key Architecture

The pipeline follows this workflow:
1. Clone target GitHub repository locally
2. Use mini-swe-agent to analyze and set up the repository in a local environment
3. Track successful commands during the agent's work
4. Extract installation/build/test commands from the successful operations
5. Generate a Dockerfile based on detected language/framework and commands
6. Optionally verify the generated Dockerfile builds and runs correctly

### Agent Configuration

The system uses two approaches:
- **Command Tracking** (`repo_to_dockerfile.py`): Wraps the environment to capture all successful commands, then post-processes them into a Dockerfile
- **Direct Generation** (`simple_repo_to_dockerfile.py`): Lets the agent directly create the Dockerfile during its analysis

## Common Commands

### Generate Dockerfile for a Repository
```bash
# Using command tracking approach
python repo_to_dockerfile.py expressjs/express --model gpt-4o-mini

# Using direct generation approach  
python simple_repo_to_dockerfile.py expressjs/express --model_name claude-sonnet-4-20250514
```

### Verify Generated Dockerfile
```bash
python verify_dockerfile.py agent-result/expressjs-express/Dockerfile --cleanup
```

### Run Mini-SWE-Agent
The mini-swe-agent submodule needs to be set up:
```bash
cd mini-swe-agent
pip install -e .
```

## Directory Structure

- `agent-result/` - Generated results organized by repository (format: owner-repo/)
  - Each subdirectory contains: Dockerfile, trajectory.json, and other analysis results
- `mini-swe-agent/` - Git submodule of the mini-swe-agent framework
- `github_repo_scraper/` - Utility for scraping GitHub repository information
- `dev-deprecated/` - Legacy/deprecated development files

## Working with Agent Results

Agent results are stored in `agent-result/<repo-name>/`:
- `Dockerfile` - Generated Dockerfile ready for use
- `trajectory.json` - Complete agent conversation and actions
- `commands_extracted.json` - List of successful commands (command tracking approach)
- `build_instructions.md` - Human-readable summary

## Environment Setup

API keys needed:
```bash
export OPENAI_API_KEY="your-key-here"
# or
export ANTHROPIC_API_KEY="your-key-here"
```

## Test Output Parsing Challenge

The repository addresses a key challenge: parsing test outputs from arbitrary repositories. Since step 1 (repository setup) is performed by an agent and typically results in all tests passing, there are limited examples of failed/non-successful test cases to learn from. Additionally, repositories use diverse testing frameworks and output formats across different programming languages.

Current approaches being explored:
- Using agents for both repository setup AND test output parsing
- Mechanistic determination of test output formats based on detected frameworks
- Parsing strategies that work across multiple languages/testing frameworks

## Language Support

The system automatically detects and supports:
- Python (pip, poetry, requirements.txt)
- Node.js (npm, yarn, package.json)
- Go (go modules)
- Rust (cargo)
- Java (Maven, Gradle)
- Ruby (bundler)
- PHP (composer)
- .NET (dotnet)

## Key Implementation Details

- **Local Environment Execution**: Agent runs in actual cloned repositories, not containers
- **Command Filtering**: Distinguishes between exploration commands and actual installation steps
- **Base Image Detection**: Automatically selects appropriate Docker base images
- **Docker Optimization**: Groups commands for efficient layer caching
- **Extended Timeouts**: Configured for long-running build processes (5+ minutes)