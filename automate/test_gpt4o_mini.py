#!/usr/bin/env python3
"""
Test script to verify GPT-4o-mini configuration works.
"""

import sys
from pathlib import Path

# Add the mini-swe-agent to path
sys.path.insert(0, str(Path(__file__).parent / "mini-swe-agent" / "src"))

def test_gpt4o_mini_config():
    """Test that GPT-4o-mini configuration works."""
    try:
        from minisweagent.models import get_model
        
        # Test with GPT-4o-mini
        model = get_model("gpt-4o-mini")
        print("✓ GPT-4o-mini model creation successful")
        print(f"  Model name: {model.config.model_name}")
        return True
    except Exception as e:
        print(f"✗ GPT-4o-mini model creation failed: {e}")
        return False

def test_model_list():
    """Test listing available models."""
    try:
        import litellm
        models = litellm.model_list
        gpt_models = [m for m in models if 'gpt' in m]
        print(f"✓ Available GPT models: {gpt_models[:5]}...")  # Show first 5
        return True
    except Exception as e:
        print(f"✗ Model listing failed: {e}")
        return False

def main():
    """Run GPT-4o-mini tests."""
    print("Testing GPT-4o-mini configuration...")
    print("=" * 40)
    
    tests = [
        test_gpt4o_mini_config,
        test_model_list
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print("=" * 40)
    print(f"Tests passed: {passed}/{len(tests)}")
    
    if passed == len(tests):
        print("🎉 GPT-4o-mini configuration is ready!")
        return 0
    else:
        print("❌ Some tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())