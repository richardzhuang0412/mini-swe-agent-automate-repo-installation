#!/bin/bash
# Script to run mini-swe-agent with GPT-4o-mini as the default model

# Set the default model
export MSWEA_MODEL_NAME="gpt-4o-mini"

# Set your OpenAI API key (you'll need to replace this with your actual key)
# export OPENAI_API_KEY="your-openai-api-key-here"

echo "Default model set to: $MSWEA_MODEL_NAME"
echo "To run the ECharts installer, execute:"
echo "  python demo_echarts_installer.py"
echo ""
echo "To run mini-swe-agent CLI with GPT-4o-mini:"
echo "  cd mini-swe-agent && python -m minisweagent.run.mini"

# Optionally run the demo
if [ "$1" = "run" ]; then
    echo "Running ECharts installer demo..."
    python demo_echarts_installer.py
fi