"""
Maven/Gradle test log parser for Java.
"""

import re
from enum import Enum

class TestStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED" 
    SKIPPED = "SKIPPED"

def parse_log_maven(log: str) -> dict[str, str]:
    """
    Parser for test logs generated with Maven or Gradle.

    Args:
        log (str): log content
    Returns:
        dict: test case to test status mapping
    """
    test_status_map = {}

    # Pattern for Maven Surefire output
    # Examples:
    # "Running com.example.TestClass"
    # "Tests run: 3, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.123 sec"
    
    # First, look for individual test methods in verbose output
    # "testMethodName(com.example.TestClass)  Time elapsed: 0.001 sec"
    # "testMethodName(com.example.TestClass)  Time elapsed: 0.001 sec  <<< FAILURE!"
    method_pattern = r"^(\w+)\([^)]+\)\s+Time elapsed:.*?(?:<<<\s+(FAILURE|ERROR)!)?$"
    
    current_class = None
    
    for line in log.split("\n"):
        line = line.strip()
        
        # Track current test class
        class_match = re.match(r"^Running\s+(.+)$", line)
        if class_match:
            current_class = class_match.group(1)
            continue
            
        # Parse individual test methods
        method_match = re.match(method_pattern, line)
        if method_match:
            method_name = method_match.group(1)
            failure_indicator = method_match.group(2)
            
            test_name = f"{current_class}.{method_name}" if current_class else method_name
            
            if failure_indicator:
                test_status_map[test_name] = TestStatus.FAILED.value
            else:
                test_status_map[test_name] = TestStatus.PASSED.value

    # Alternative pattern for JUnit-style output
    if not test_status_map:
        # Look for JUnit XML-style patterns in console output
        junit_pattern = r"^\s*(PASS|FAIL|SKIP).*?(\w+\.\w+).*$"
        for line in log.split("\n"):
            match = re.match(junit_pattern, line.strip())
            if match:
                status, test_name = match.groups()
                if status == "PASS":
                    test_status_map[test_name] = TestStatus.PASSED.value
                elif status == "FAIL":
                    test_status_map[test_name] = TestStatus.FAILED.value
                elif status == "SKIP":
                    test_status_map[test_name] = TestStatus.SKIPPED.value

    # Gradle test output pattern
    if not test_status_map:
        # "com.example.TestClass > testMethod PASSED"
        gradle_pattern = r"^(.+?)\s+>\s+(\w+)\s+(PASSED|FAILED|SKIPPED)$"
        for line in log.split("\n"):
            match = re.match(gradle_pattern, line.strip())
            if match:
                class_name, method_name, status = match.groups()
                test_name = f"{class_name}.{method_name}"
                
                if status == "PASSED":
                    test_status_map[test_name] = TestStatus.PASSED.value
                elif status == "FAILED":
                    test_status_map[test_name] = TestStatus.FAILED.value
                elif status == "SKIPPED":
                    test_status_map[test_name] = TestStatus.SKIPPED.value

    return test_status_map