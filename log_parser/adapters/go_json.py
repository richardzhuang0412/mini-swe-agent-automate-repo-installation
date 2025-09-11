"""
Go test JSON parser adapter.

Parses Go test JSON output format (go test -json).
"""

import json
from pathlib import Path
from typing import Dict, Optional, Any, List
from ..schemas.output import TestResults, TestCase, OverallResult, ParserMeta, calculate_overall_status
from ..utils.text_utils import create_stable_test_id, truncate_message


class GoTestJSONParser:
    """Parser for Go test JSON format results"""
    
    def parse_file(self, json_path: Path) -> Optional[TestResults]:
        """
        Parse a Go test JSON file and return unified test results.
        
        Note: Go test JSON is newline-delimited JSON (one JSON object per line).
        
        Args:
            json_path: Path to the Go test JSON file
            
        Returns:
            TestResults or None if parsing fails
        """
        if not json_path.exists():
            return None
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            json_objects = []
            for line in lines:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        json_objects.append(obj)
                    except json.JSONDecodeError:
                        continue  # Skip malformed lines
            
            return self._parse_go_json_objects(json_objects, str(json_path))
        except IOError:
            return None
    
    def parse_string(self, json_content: str) -> Optional[TestResults]:
        """
        Parse Go test JSON from a string (newline-delimited JSON).
        
        Args:
            json_content: JSON content as string
            
        Returns:
            TestResults or None if parsing fails
        """
        try:
            lines = json_content.strip().split('\n')
            json_objects = []
            
            for line in lines:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        json_objects.append(obj)
                    except json.JSONDecodeError:
                        continue
            
            return self._parse_go_json_objects(json_objects, "json_content")
        except Exception:
            return None
    
    def _parse_go_json_objects(self, json_objects: List[Dict[str, Any]], source: str) -> TestResults:
        """Parse a list of Go test JSON objects"""
        tests = {}
        packages = {}  # Track package-level results
        
        start_time = None
        end_time = None
        
        for obj in json_objects:
            self._process_json_object(obj, tests, packages)
            
            # Track timing
            if 'Time' in obj:
                timestamp = obj['Time']
                if start_time is None:
                    start_time = timestamp
                end_time = timestamp
        
        # Calculate overall statistics
        total_tests = len(tests)
        passed_tests = sum(1 for test in tests.values() if test.status == 'pass')
        failed_tests = sum(1 for test in tests.values() if test.status == 'fail')
        skipped_tests = sum(1 for test in tests.values() if test.status == 'skip')
        error_tests = sum(1 for test in tests.values() if test.status == 'error')
        
        # Determine exit code based on failures
        exit_code = 1 if (failed_tests + error_tests) > 0 else 0
        
        # Check if any packages failed to build
        for pkg_info in packages.values():
            if pkg_info.get('action') == 'fail' and 'Test' not in pkg_info.get('test', ''):
                exit_code = 1  # Build failure
                break
        
        overall_status = calculate_overall_status(tests, exit_code)
        
        # Calculate duration
        duration_s = None
        if start_time and end_time:
            try:
                from datetime import datetime
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                duration_s = (end_dt - start_dt).total_seconds()
            except:
                duration_s = None
        
        overall = OverallResult(
            status=overall_status,
            exit_code=exit_code,
            duration_s=duration_s,
            total_tests=total_tests,
            passed=passed_tests,
            failed=failed_tests,
            skipped=skipped_tests,
            errors=error_tests
        )
        
        meta = ParserMeta(
            runner="go-test",
            detected_by=[source],
            confidence=1.0,
            structured_format=True
        )
        
        return TestResults(
            overall=overall,
            tests=tests,
            meta=meta
        )
    
    def _process_json_object(self, obj: Dict[str, Any], tests: Dict[str, TestCase], packages: Dict[str, Dict]):
        """Process a single JSON object from Go test output"""
        action = obj.get('Action')
        test_name = obj.get('Test')
        package = obj.get('Package', '')
        
        if not action:
            return
        
        if test_name:
            # This is a test-level event
            self._process_test_event(obj, tests)
        else:
            # This is a package-level event
            if package:
                if package not in packages:
                    packages[package] = {}
                packages[package].update(obj)
    
    def _process_test_event(self, obj: Dict[str, Any], tests: Dict[str, TestCase]):
        """Process a test-level event"""
        action = obj.get('Action')
        test_name = obj.get('Test')
        package = obj.get('Package', '')
        
        if not test_name:
            return
        
        # Create test ID
        test_id = create_stable_test_id(package, None, test_name)
        
        # Get or create test case
        if test_id not in tests:
            tests[test_id] = TestCase(
                status='error',  # Default, will be updated
                file=package,
                line=None,
                duration_s=None,
                message=None,
                stdout=None,
                stderr=None
            )
        
        test_case = tests[test_id]
        
        if action == 'run':
            # Test started
            test_case.status = 'pass'  # Assume pass until we hear otherwise
        
        elif action == 'pass':
            # Test passed
            test_case.status = 'pass'
            elapsed = obj.get('Elapsed')
            if elapsed:
                test_case.duration_s = elapsed
        
        elif action == 'fail':
            # Test failed
            test_case.status = 'fail'
            elapsed = obj.get('Elapsed')
            if elapsed:
                test_case.duration_s = elapsed
        
        elif action == 'skip':
            # Test skipped
            test_case.status = 'skip'
        
        elif action == 'output':
            # Test output
            output = obj.get('Output', '')
            
            # Accumulate output - Go can send multiple output events per test
            if output.strip():
                if 'FAIL:' in output or 'panic:' in output:
                    # This looks like failure output
                    if test_case.message:
                        test_case.message += '\n' + output
                    else:
                        test_case.message = output
                    test_case.message = truncate_message(test_case.message)
                else:
                    # Regular output
                    if test_case.stdout:
                        test_case.stdout += output
                    else:
                        test_case.stdout = output
        
        # Update the test case in the dictionary
        tests[test_id] = test_case


def find_go_json_files(directory: Path) -> List[Path]:
    """Find Go test JSON result files in a directory tree"""
    patterns = [
        "go-test-*.json",
        "**/test-results/go*.json",
        "**/results/go*.json"
    ]
    
    found_files = []
    for pattern in patterns:
        try:
            matches = list(directory.glob(pattern))
            found_files.extend(matches)
        except:
            continue
    
    return list(set(found_files))