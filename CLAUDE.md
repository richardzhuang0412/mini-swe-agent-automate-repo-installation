# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository implements a **complete and production-ready** 3-stage automated pipeline that converts GitHub repositories into SWE-smith compatible profile classes. It uses mini-swe-agent to analyze repositories, create deployment artifacts (Dockerfiles or conda scripts), verify installations with smart parsing, and generate ready-to-integrate profile classes with correct naming conventions and metadata.

**Current Status:** ✅ **COMPLETE** - Full end-to-end pipeline operational with SWE-smith integration

## Core Architecture: 3-Stage Pipeline

### Stage 1: Repository Analysis & Artifact Generation
**Script**: `simple_repo_to_dockerfile.py`
- **Purpose**: Analyzes repositories and generates deployment artifacts
- **Python repos** (with `--python-repo`): Creates conda installation scripts compatible with SWE-smith workflow
- **Non-Python repos**: Creates Dockerfiles with proper base image detection
- **Output**: `repo_metadata.json` + deployment artifact (`.sh` script or `Dockerfile`)
- **Agent configs**: `conda_installation_generation.yaml` or `dockerfile_generation.yaml`

### Stage 2: Build Verification & Test Execution
**Script**: `verify_dockerfile.py`
- **Purpose**: Separates installation verification from testing verification with detailed reporting
- **Python repos**: Uses SWE-smith compatible workflow - clones repository, creates conda environment with "testbed" name, runs installation script, executes tests from cloned repo
- **Non-Python repos**: Docker build success = installation check passed, intelligent test result parsing = testing check passed
- **Key Feature**: Returns separate status for installation success and testing success
- **Smart Parsing**: Ignores npm notices and exit code noise, focuses on actual test results
- **Output**: `test_output.txt` with captured test results + detailed verification summary

### Stage 3: Test Output Parsing
**Script**: `verify_testing.py`
- **Purpose**: Parse test outputs using framework-specific parsers
- **Parser selection**: Framework match → language match → fallback strategy
- **Output**: `parsed_test_status.json` with test status mapping and identified parser

### Master Orchestrator: End-to-End Profile Generation
**Script**: `generate_profile.py` ⭐ **RECOMMENDED**
- **Purpose**: Runs all 3 stages and generates SWE-smith compatible profile classes
- **Features**:
  - 🔴 **Livestream output** - See agent work in real-time during Stage 1
  - 🛑 **Smart failure handling** - Pipeline stops on stage failures (Stage 1→2→3)
  - 📋 **Complete logging** - Full pipeline output saved to `pipeline_full_log.txt`
  - 🎯 **SWE-smith integration** - Zero-friction profile classes with correct naming
- **Output**: Ready-to-integrate profile classes in `generated_profiles/` directory

## Common Commands

### End-to-End Profile Generation (Recommended)
```bash
# Python repository - generates conda-based profile
python generate_profile.py Instagram/MonkeyType --python-repo --model claude-sonnet-4-20250514

# JavaScript repository - generates Docker-based profile
python generate_profile.py expressjs/express --model claude-sonnet-4-20250514

# Output profile class to file
python generate_profile.py fastapi/typer --python-repo --output fastapi_typer_profile.py
```

### Individual Stage Execution
```bash
# Stage 1: Generate conda script + metadata
python simple_repo_to_dockerfile.py owner/repo --python-repo --model_name claude-sonnet-4-20250514

# Stage 2: Verify installation and run tests (with separate install/test checks)
python verify_dockerfile.py agent-result/owner-repo --python-repo --cleanup

# Stage 3: Parse test output
python verify_testing.py agent-result/owner-repo --python-repo
```

### Verification-Only Commands
```bash
# Verify non-Python repo Dockerfile (separate installation and testing checks)
python verify_dockerfile.py agent-result/owner-repo/Dockerfile --cleanup

# Verify Python repo with SWE-smith workflow
python verify_dockerfile.py agent-result/owner-repo --python-repo
```

### Extended Timeout for Complex Repositories
```bash
# For repositories requiring longer analysis/build time
timeout 300 python generate_profile.py complex/repo --model claude-sonnet-4-20250514
```

## Key Data Formats

### repo_metadata.json (Standardized Format)
```json
{
  "install_commands": ["pip install -e .", "pip install pytest"],
  "test_commands": ["pytest -v", "python -m pytest --verbose"],
  "language": "python",
  "test_framework": "pytest",
  "commit_hash": "git-commit-hash-here"
}
```

### parsed_test_status.json
```json
{
  "parser": "pytest",
  "parsed_test_status": {
    "test_module.py::test_function": "PASSED",
    "test_module.py::test_other": "FAILED"
  }
}
```

## Repository Type Handling

### Python Repositories (`--python-repo` flag)
- **Environment**: Conda-based isolation with "testbed" environment name (required by SWE-smith)
- **Verification Workflow**:
  1. Clone repository at specified commit
  2. Run conda installation script in cloned repo directory
  3. Export conda environment to YAML for SWE-smith compatibility
  4. Execute tests from within cloned repository (not from agent-result directory)
- **Compatibility**: Full SWE-smith try_install_py workflow integration (adapted locally)
- **Default Python**: 3.10 unless repository specifies otherwise
- **Installation pattern**: Conda environment creation → pip package installation
- **Required script boilerplate**: Standardized conda detection paths

### Non-Python Repositories
- **Environment**: Docker containerization
- **Verification Workflow**:
  1. Docker build success → Installation Check PASSED
  2. Smart test result parsing → Testing Check PASSED/FAILED
  3. Ignores npm notices and exit code noise, focuses on actual test counts
- **Supported languages**: JavaScript (Node.js), Go, Rust, Java, PHP, Ruby, .NET
- **Base image detection**: Automatic selection (node:18-slim, golang:1.21, rust:latest, etc.)
- **Package managers**: Native tools (npm, yarn, cargo, maven, composer, etc.)
- **Smart Test Parsing**: Framework-aware parsing (mocha, jest, etc.) with pattern matching for test results

## Test Output Parsing System

### Supported Test Frameworks
- **JavaScript**: Jest, Mocha
- **Python**: PyTest (with embedded custom parser logic)
- **Go**: go test
- **Rust**: Cargo test
- **Java**: Maven Surefire

### Parser Selection Strategy
1. **Priority 1**: Exact framework match from metadata
2. **Priority 2**: Try all parsers for detected language
3. **Priority 3**: Fallback to all remaining parsers

## Directory Structure

- `agent-result/owner-repo/` - Results for each repository analysis
  - `repo_metadata.json` - Standardized repository metadata
  - `Dockerfile` or `*_install.sh` - Generated deployment artifact
  - `test_output.txt` - Captured test execution output
  - `parsed_test_status.json` - Test parsing results
  - `pipeline_full_log.txt` - Complete pipeline execution log
  - `trajectory.json` - Complete agent interaction log
  - `generated_profiles/` - **🎯 SWE-smith Integration Files**
    - `profile_class.py` - Ready-to-copy profile class
    - `profile_metadata.json` - Integration metadata
    - `integration_instructions.md` - Step-by-step integration guide
- `log_parser/` - Test output parsing framework with language-specific parsers
- `mini-swe-agent/` - Git submodule of the analysis framework

## Environment Setup

Required API keys:
```bash
export OPENAI_API_KEY="your-key-here"
# or
export ANTHROPIC_API_KEY="your-key-here"
```

Mini-swe-agent installation:
```bash
cd mini-swe-agent
pip install -e .
```

## Model Recommendations

- **Accuracy**: `claude-sonnet-4-20250514` for complex repositories requiring precise analysis
- **Speed**: `gpt-4o-mini` for faster iteration and simpler repositories
- **Livestream mode**: Add `--livestream` flag to see real-time agent interactions

## Key Implementation Details

### SWE-smith Integration ✅ **COMPLETE**
- **Profile Class Generation**: Clean, import-free classes with correct `{RepoName}{CommitHash8}` naming
- **Python repositories**: Generated conda scripts directly compatible with try_install_py workflow
- **Standardized environment**: "testbed" conda environment name requirement
- **Metadata format**: Matches SWE-smith profile registry expectations
- **Zero-friction integration**: Ready-to-copy profile classes with detailed instructions
- **Integration metadata**: Tracks pipeline success and integration readiness

### Profile Class Generation
- **Python profiles**: Conda-based with embedded installation commands and custom pytest parser
- **JavaScript profiles**: Docker-based with framework-specific parser imports
- **Generic profiles**: Language-agnostic with detected base images and parser functions
- **Ready-to-use**: Generated classes include all necessary imports and methods

### Error Handling & Recovery
- **Pipeline continuation**: Stages continue executing even if previous stages fail
- **Graceful degradation**: Falls back to basic profiles when parsing fails
- **Real-time feedback**: Live output streaming during long-running operations
- **Resource cleanup**: Automatic Docker image and temporary file cleanup

### Extended Timeout Support
- **Build operations**: 10-15 minute timeouts for complex repository builds
- **Test execution**: Extended timeouts for comprehensive test suites
- **Agent interactions**: Configurable timeouts for repository analysis phases

## ✅ **Current Development Status (Latest)**

### **Pipeline Status: PRODUCTION READY**
- ✅ **All 3 stages operational** with smart failure handling
- ✅ **SWE-smith integration complete** with correct naming conventions
- ✅ **Multi-language support verified** (Python, JavaScript, Rust)
- ✅ **Smart verification system** separating installation from testing
- ✅ **Livestream functionality** for real-time agent observation
- ✅ **Complete logging system** with pipeline traces

### **Testing Results (Verified Repositories)**

**Python Repositories (Conda-based):**
- ✅ **Instagram/MonkeyType** → `MonkeyType15e7bca6` (379 tests passed)
- ✅ **fastapi/typer** → `Typerdc07284d` (CLI framework)
- ✅ **Textualize/rich** → `Richea9d4db5` (Rich text library)

**JavaScript Repositories (Docker-based):**
- ✅ **expressjs/express** → `Express9a7afb28` (1235 tests passed, mocha)
- ✅ **facebook/react** → `React720bb130` (Jest framework)

**Rust Repositories (Generic profile):**
- ✅ **rust-lang/cargo** → `Cargoc86bc374` (Cargo test framework)

### **Recent Major Improvements**
1. **SWE-smith Profile Storage System** (Complete)
   - Clean profile classes without imports
   - Correct `{RepoName}{CommitHash8}` naming convention
   - Integration metadata and instructions

2. **Pipeline Failure Handling** (Complete)
   - Early termination on stage failures
   - Clear error reporting and stage status

3. **Smart Verification Logic** (Complete)
   - Separate installation vs testing checks
   - Python: SWE-smith compatible conda workflow
   - Non-Python: Docker build + intelligent test parsing

4. **Livestream Functionality** (Complete)
   - Real-time Stage 1 output display
   - Full pipeline logging to files

5. **Quality Assurance System** (Complete)
   - Profile generation only proceeds if Stages 1&2 succeed
   - Stage 1 required for repository analysis and metadata
   - Stage 2 required for installation/testing verification
   - Stage 3 failure allows profile generation with defaults

## Debugging Pipeline Issues

### Common Issues
1. **Stage 2 verification false failures**: Check if tests actually passed but npm notices caused exit code issues - use smart parsing
2. **Python repo test execution**: Verify repository actually contains tests in expected locations and tests run from cloned repo directory
3. **Docker build failures**: Check base image availability and dependency resolution
4. **Installation vs Testing separation**: Installation can succeed while testing fails - both are reported separately

### Troubleshooting Commands
```bash
# Check what files were generated
ls -la agent-result/owner-repo/

# Examine test output for actual test results
cat agent-result/owner-repo/test_output.txt

# Re-run Stage 2 verification with detailed output
python verify_dockerfile.py agent-result/owner-repo --python-repo

# Check if conda environment YAML was generated (Python repos)
ls -la agent-result/owner-repo/*.yml

# Review agent trajectory for analysis details
head -100 agent-result/owner-repo/trajectory.json
```