# GitHub Repository to Dockerfile Generator

This tool automatically analyzes GitHub repositories and generates Dockerfiles that can reproduce the complete installation and testing process.

## How It Works

1. **Clone Repository**: Downloads the specified GitHub repo locally
2. **Agent Analysis**: Uses mini-swe-agent in a local environment to figure out how to install and test the project
3. **Command Extraction**: Tracks all successful commands the agent used
4. **Dockerfile Generation**: Creates a Dockerfile with the extracted steps
5. **Verification**: Optional testing to ensure the Dockerfile works

## Key Features

- ✅ **Local Environment Analysis**: Agent runs in the actual cloned repo (no predefined Docker assumptions)
- ✅ **Dynamic Base Image Detection**: Automatically determines the right Docker base image
- ✅ **Command Tracking**: Records all successful installation steps
- ✅ **Multi-Language Support**: Works with Python, Node.js, Go, Rust, Java, Ruby, PHP, etc.
- ✅ **Dockerfile Optimization**: Groups commands efficiently for Docker layer caching
- ✅ **Verification Tools**: Test generated Dockerfiles to ensure they work

## Installation

1. Ensure you have mini-swe-agent set up:
   ```bash
   cd mini-swe-agent
   pip install -e .
   ```

2. Set up your API key:
   ```bash
   export OPENAI_API_KEY="your-key-here"
   # or
   export ANTHROPIC_API_KEY="your-key-here"
   ```

## Usage

### Basic Usage

```bash
# Generate Dockerfile for Express.js
python repo_to_dockerfile.py expressjs/express --model gpt-4o-mini

# Generate Dockerfile for Python requests library  
python repo_to_dockerfile.py psf/requests --model claude-sonnet-4-20250514

# Use custom workspace directory
python repo_to_dockerfile.py facebook/react --workspace ./my_analysis
```

### Command Line Options

```bash
python repo_to_dockerfile.py <github_repo> [options]

Options:
  --model MODEL       AI model to use (default: gpt-4o-mini)
  --workspace DIR     Workspace directory (default: ./workspace)
  
Examples:
  python repo_to_dockerfile.py numpy/numpy
  python repo_to_dockerfile.py tensorflow/tensorflow --model claude-sonnet-4-20250514
```

### Verification

Test that your generated Dockerfile actually works:

```bash
# Verify the generated Dockerfile
python verify_dockerfile.py workspace/express --cleanup

# Custom verification
python verify_dockerfile.py ./my_repo --dockerfile ./custom/Dockerfile --image-name my-test
```

## Output Structure

After running the tool, you'll get:

```
workspace/
└── <repo-name>/
    ├── <original repo files>
    └── agent-result/
        ├── Dockerfile                    # 🐳 Ready-to-use Dockerfile
        ├── commands_extracted.json       # 📝 Raw command list  
        ├── agent_conversation.json       # 💬 Full AI conversation
        └── build_instructions.md         # 📋 Human-readable summary
```

## Example Output

### For `expressjs/express`:

**Generated Dockerfile:**
```dockerfile
# Generated Dockerfile for expressjs/express
# Base image determined from analysis: node:18-slim
FROM node:18-slim

# Set working directory
WORKDIR /app

# Copy repository contents
COPY . .

# Setup and build
RUN npm install && \
    npm ci

# Verify installation by running tests
RUN npm test

# Default command
CMD ["/bin/bash"]
```

**Extracted Commands:**
```json
[
  "npm install",
  "npm ci", 
  "npm test",
  "npm run lint"
]
```

## How the Agent Works

The agent runs in the **local environment** where your repo is cloned and follows this process:

1. **🔍 Exploration Phase**: 
   - Examines repository structure
   - Identifies language, build system, package managers
   - Reads documentation and config files

2. **🏗️ Installation Phase**:
   - Installs system dependencies if needed
   - Runs appropriate package managers (npm, pip, cargo, etc.)
   - Follows project-specific setup instructions

3. **🧪 Testing Phase**:
   - Locates test commands
   - Runs the test suite
   - Verifies everything works

4. **📦 Dockerfile Generation**:
   - Extracts only the successful commands
   - Determines appropriate Docker base image
   - Optimizes for Docker layer caching
   - Adds proper structure (WORKDIR, COPY, etc.)

## Supported Languages/Frameworks

The tool dynamically detects and supports:

- **Python**: pip, poetry, pipenv, requirements.txt, setup.py
- **Node.js**: npm, yarn, package.json, TypeScript  
- **Go**: go modules, go.mod, go.sum
- **Rust**: cargo, Cargo.toml
- **Java**: Maven, Gradle, pom.xml, build.gradle
- **Ruby**: bundler, Gemfile
- **PHP**: composer, composer.json
- **C#/.NET**: dotnet, .csproj

## Troubleshooting

### Common Issues

1. **"No installation commands found"**
   - The agent may have failed to complete the analysis
   - Check the agent conversation log in `agent_conversation.json`
   - Try with a different model or increase cost limits

2. **"Docker build failed"**
   - Check the generated Dockerfile for syntax issues
   - Some commands may not translate well to Docker environment
   - Manual adjustments might be needed

3. **API rate limits**
   - Use a different model
   - Check your API key and billing status

### Debug Mode

For more detailed output, you can examine:
- `agent_conversation.json` - Full conversation with the AI
- `commands_extracted.json` - All commands that were tracked
- The terminal output shows real-time progress

## Advanced Usage

### Custom Agent Configuration

You can modify the agent behavior by editing the `DockerfileAgentConfig` in `repo_to_dockerfile.py`:

```python
@dataclass
class DockerfileAgentConfig(AgentConfig):
    step_limit: int = 100        # More steps for complex repos
    cost_limit: float = 15.0     # Higher budget for thorough analysis
```

### Custom Base Images

The tool automatically detects appropriate base images, but you can modify the `detect_base_image_from_commands()` function to use custom images.

### Integration with CI/CD

```bash
# In your CI pipeline
python repo_to_dockerfile.py $GITHUB_REPOSITORY --model gpt-4o-mini
python verify_dockerfile.py workspace/$(basename $GITHUB_REPOSITORY)
docker build -f workspace/$(basename $GITHUB_REPOSITORY)/agent-result/Dockerfile .
```

## Examples

### Python Project (requests)
```bash
python repo_to_dockerfile.py psf/requests
# Generates Dockerfile with: python:3.11-slim, pip install, pytest
```

### Node.js Project (Express)  
```bash
python repo_to_dockerfile.py expressjs/express
# Generates Dockerfile with: node:18-slim, npm install, npm test
```

### Go Project
```bash
python repo_to_dockerfile.py gin-gonic/gin
# Generates Dockerfile with: golang:1.21-alpine, go mod download, go test
```

## Contributing

The tool is designed to be easily extensible:

1. **Add language support**: Modify `detect_base_image_from_commands()` and `language_indicators`
2. **Improve command filtering**: Enhance `get_installation_commands()` logic
3. **Better Dockerfile optimization**: Extend `generate_dockerfile()` function

## Limitations

- Requires repositories that can be analyzed programmatically
- Some complex build processes might need manual Dockerfile adjustments  
- System-level dependencies might need refinement
- Works best with well-documented repositories

---

**🚀 Ready to containerize any GitHub repository automatically!**