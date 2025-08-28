#!/usr/bin/env python3
"""
Demo script for automatically installing the apache/echarts JavaScript repository using GPT-4o-mini.
"""

import sys
import os
from pathlib import Path

# Add the mini-swe-agent to path
sys.path.insert(0, str(Path(__file__).parent / "mini-swe-agent" / "src"))

from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model
from minisweagent.environments.docker import DockerEnvironment
from minisweagent.run.utils.save import save_traj


def create_echarts_installer(model_name="gpt-4o-mini"):
    """
    Create an agent configured specifically for installing apache/echarts.
    
    Args:
        model_name (str): Name of the model to use
        
    Returns:
        DefaultAgent: Configured agent instance
    """
    # Create the agent with Docker environment for isolation
    agent = DefaultAgent(
        get_model(model_name, config={"model_name": model_name}),
        DockerEnvironment(
            image="node:18",
            cwd="/workspace",
            env={
                "DEBIAN_FRONTEND": "noninteractive",
                "NODE_ENV": "development",
                "CI": "true"  # Disable interactive prompts
            },
            timeout=600,  # 10 minutes per command for complex builds
            container_timeout="4h"  # 4 hour container lifetime
        ),
        # Custom configuration for echarts installation
        system_template="""You are an expert JavaScript/Node.js developer specializing in repository installation and testing.

Your response must contain exactly ONE bash code block with ONE command.
Include a THOUGHT section before your command explaining your reasoning.

Focus on:
1. Cloning the apache/echarts repository
2. Identifying the project structure and dependencies
3. Installing all required dependencies correctly
4. Running the test suite
5. Verifying tests pass

Response format:
THOUGHT: Explain your reasoning and what you plan to do
```bash
single_command_here
```""",
        
        instance_template="""Install and test the apache/echarts repository.

Repository: https://github.com/apache/echarts

Workflow:
1. Clone the repository to /workspace
2. Analyze the project structure to identify how to install dependencies
3. Install all required dependencies using npm/yarn
4. Find and run the test suite
5. Report the test results
6. When complete, run: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT

Apache ECharts is a complex JavaScript visualization library, so:
- Look for package.json and lock files
- Check for build scripts in package.json
- Look for test commands in package.json
- The project might use npm, yarn, or other tools
- Tests might include unit tests, integration tests, or visual tests
- Be patient as building and testing might take time""",
        
        cost_limit=15.0,  # Higher cost limit for complex project
        step_limit=150    # More steps for complex project
    )
    
    return agent


def main():
    """Main function to install apache/echarts."""
    model_name = sys.argv[1] if len(sys.argv) > 1 else "gpt-4o-mini"
    
    print(f"Creating agent for apache/echarts repository")
    print(f"Using model: {model_name}")
    print(f"Base image: node:18")
    
    # Create the agent
    agent = create_echarts_installer(model_name)
    
    # Define the task
    task = "Clone the apache/echarts repository from https://github.com/apache/echarts, install all dependencies, and run the test suite. Report whether tests pass."
    
    try:
        print("\nRunning echarts installation task...")
        print("This may take 10-30 minutes as ECharts is a large project...")
        exit_status, result = agent.run(task)
        
        print(f"\nTask completed with exit status: {exit_status}")
        print(f"Result: {result}")
        
        # Save the trajectory
        output_file = Path("echarts_installation.traj.json")
        save_traj(
            agent,
            output_file,
            exit_status=exit_status,
            result=result,
            extra_info={
                "repo_url": "https://github.com/apache/echarts",
                "model_name": model_name,
                "base_image": "node:18"
            }
        )
        print(f"Trajectory saved to: {output_file}")
        
        # Also save a simple summary
        summary_file = Path("echarts_installation_summary.txt")
        summary_content = f"""ECharts Installation Summary
========================

Repository: https://github.com/apache/echarts
Model: {model_name}
Exit Status: {exit_status}
Result: {result}

Model Statistics:
- API Calls: {agent.model.n_calls}
- Total Cost: ${agent.model.cost:.4f}

Conversation Length: {len(agent.messages)} messages
"""
        summary_file.write_text(summary_content)
        print(f"Summary saved to: {summary_file}")
        
    except Exception as e:
        print(f"Error during installation: {e}")
        import traceback
        traceback.print_exc()
        
        # Save error trajectory
        output_file = Path("echarts_installation_error.traj.json")
        save_traj(
            agent,
            output_file,
            exit_status=type(e).__name__,
            result=str(e),
            extra_info={
                "repo_url": "https://github.com/apache/echarts",
                "model_name": model_name,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
        print(f"Error trajectory saved to: {output_file}")


if __name__ == "__main__":
    main()