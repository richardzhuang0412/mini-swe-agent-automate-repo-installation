#!/usr/bin/env python3
"""
Simple test script to verify mini-swe-agent installation and basic functionality.
"""

import sys
from pathlib import Path

# Add the mini-swe-agent to path
sys.path.insert(0, str(Path(__file__).parent / "mini-swe-agent" / "src"))

def test_imports():
    """Test that all required modules can be imported."""
    try:
        from minisweagent.agents.default import DefaultAgent
        from minisweagent.models.test_models import DeterministicModel
        from minisweagent.environments.local import LocalEnvironment
        print("✓ All basic imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_model_creation():
    """Test creating a model instance."""
    try:
        from minisweagent.models.test_models import DeterministicModel
        model = DeterministicModel(outputs=["```bash\necho 'test'\n```"])
        print("✓ Model creation successful")
        return True
    except Exception as e:
        print(f"✗ Model creation failed: {e}")
        return False

def test_agent_creation():
    """Test creating an agent instance."""
    try:
        from minisweagent.agents.default import DefaultAgent
        from minisweagent.models.test_models import DeterministicModel
        from minisweagent.environments.local import LocalEnvironment
        
        model = DeterministicModel(outputs=["```bash\necho 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'\necho 'test complete'\n```"])
        
        agent = DefaultAgent(
            model,
            LocalEnvironment(timeout=10),
            cost_limit=1.0,
            step_limit=5
        )
        print("✓ Agent creation successful")
        return True
    except Exception as e:
        print(f"✗ Agent creation failed: {e}")
        return False

def test_simple_task():
    """Test running a simple task."""
    try:
        from minisweagent.agents.default import DefaultAgent
        from minisweagent.models.test_models import DeterministicModel
        from minisweagent.environments.local import LocalEnvironment
        
        model = DeterministicModel(outputs=["```bash\necho 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'\necho 'Hello, World!'\n```"])
        
        agent = DefaultAgent(
            model,
            LocalEnvironment(timeout=10),
            cost_limit=1.0,
            step_limit=5
        )
        
        exit_status, result = agent.run("Say hello world")
        
        if exit_status == "Submitted" and "Hello, World!" in result:
            print("✓ Simple task execution successful")
            return True
        else:
            print(f"✗ Simple task execution failed: exit_status={exit_status}, result={result}")
            return False
            
    except Exception as e:
        print(f"✗ Simple task execution failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing mini-swe-agent basic functionality...")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_model_creation,
        test_agent_creation,
        test_simple_task
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{len(tests)}")
    
    if passed == len(tests):
        print("🎉 All tests passed! mini-swe-agent is ready to use.")
        return 0
    else:
        print("❌ Some tests failed. Please check the installation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())