"""
Jest JSON parser adapter.

Parses Jest JSON output format (jest --json).
"""

import json
from pathlib import Path
from typing import Dict, Optional, Any
from ..schemas.output import TestResults, TestCase, OverallResult, ParserMeta, calculate_overall_status
from ..utils.text_utils import create_stable_test_id, truncate_message


class JestJSONParser:
    """Parser for Jest JSON format test results"""
    
    def parse_file(self, json_path: Path) -> Optional[TestResults]:
        """
        Parse a Jest JSON file and return unified test results.
        
        Args:
            json_path: Path to the Jest JSON file
            
        Returns:
            TestResults or None if parsing fails
        """
        if not json_path.exists():
            return None
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return self._parse_jest_data(data, str(json_path))
        except (json.JSONDecodeError, IOError):
            return None
    
    def parse_string(self, json_content: str) -> Optional[TestResults]:
        """
        Parse Jest JSON from a string.
        
        Args:
            json_content: JSON content as string
            
        Returns:
            TestResults or None if parsing fails
        """
        try:
            data = json.loads(json_content)
            return self._parse_jest_data(data, "json_content")
        except json.JSONDecodeError:
            return None
    
    def _parse_jest_data(self, data: Dict[str, Any], source: str) -> TestResults:
        """Parse Jest JSON data structure"""
        tests = {}
        
        # Extract overall statistics
        total_tests = data.get('numTotalTests', 0)
        passed_tests = data.get('numPassedTests', 0)
        failed_tests = data.get('numFailedTests', 0)
        skipped_tests = data.get('numPendingTests', 0) + data.get('numTodoTests', 0)
        
        # Calculate duration - Jest reports in milliseconds
        start_time = data.get('startTime', 0)
        end_time = start_time
        if 'testResults' in data:
            for test_suite in data['testResults']:
                suite_start = test_suite.get('startTime', start_time)
                suite_end = test_suite.get('endTime', suite_start)
                end_time = max(end_time, suite_end)
        
        duration_s = (end_time - start_time) / 1000.0 if end_time > start_time else None
        
        # Parse individual test results
        test_results = data.get('testResults', [])
        for test_suite in test_results:
            suite_tests = self._parse_test_suite(test_suite)
            tests.update(suite_tests)
        
        # Determine overall status
        success = data.get('success', failed_tests == 0)
        exit_code = 0 if success else 1
        overall_status = calculate_overall_status(tests, exit_code)
        
        overall = OverallResult(
            status=overall_status,
            exit_code=exit_code,
            duration_s=duration_s,
            total_tests=total_tests,
            passed=passed_tests,
            failed=failed_tests,
            skipped=skipped_tests,
            errors=0  # Jest doesn't typically distinguish errors from failures
        )
        
        meta = ParserMeta(
            runner="jest",
            detected_by=[source],
            confidence=1.0,
            structured_format=True
        )
        
        return TestResults(
            overall=overall,
            tests=tests,
            meta=meta
        )
    
    def _parse_test_suite(self, test_suite: Dict[str, Any]) -> Dict[str, TestCase]:
        """Parse a single test suite from Jest results"""
        tests = {}
        test_file = test_suite.get('name', '')  # Full file path
        
        # Extract just filename for cleaner test IDs
        file_name = Path(test_file).name if test_file else None
        
        assertion_results = test_suite.get('assertionResults', [])
        
        for assertion in assertion_results:
            test_case = self._parse_assertion_result(assertion, file_name)
            if test_case:
                test_id, test_case_obj = test_case
                tests[test_id] = test_case_obj
        
        return tests
    
    def _parse_assertion_result(self, assertion: Dict[str, Any], file_name: Optional[str]) -> Optional[tuple]:
        """Parse a single test assertion result"""
        test_title = assertion.get('title', '')
        full_name = assertion.get('fullName', test_title)
        
        # Extract ancestor titles to build suite path
        ancestor_titles = assertion.get('ancestorTitles', [])
        suite_path = ' > '.join(ancestor_titles) if ancestor_titles else None
        
        # Create test ID
        test_id = create_stable_test_id(file_name, suite_path, test_title)
        
        # Parse status
        status_map = {
            'passed': 'pass',
            'failed': 'fail',
            'pending': 'skip',
            'todo': 'skip',
            'disabled': 'skip'
        }
        jest_status = assertion.get('status', 'unknown')
        status = status_map.get(jest_status, 'error')
        
        # Parse duration (Jest reports in milliseconds)
        duration = None
        duration_ms = assertion.get('duration')
        if duration_ms is not None:
            duration = duration_ms / 1000.0
        
        # Extract failure information
        message = None
        if status in ['fail', 'error']:
            failure_messages = assertion.get('failureMessages', [])
            if failure_messages:
                # Combine all failure messages
                message = '\n'.join(failure_messages)
                message = truncate_message(message)
        
        # Extract location information
        location = assertion.get('location')
        line = None
        if location:
            line = location.get('line')
        
        test_case = TestCase(
            status=status,
            file=file_name,
            line=line,
            duration_s=duration,
            message=message,
            stdout=None,  # Jest JSON doesn't typically include stdout/stderr per test
            stderr=None
        )
        
        return test_id, test_case


def find_jest_json_files(directory: Path) -> list[Path]:
    """Find Jest JSON result files in a directory tree"""
    patterns = [
        "jest-results*.json",
        "**/results/jest*.json",
        "**/test-results/jest*.json",
        "**/coverage/jest*.json"
    ]
    
    found_files = []
    for pattern in patterns:
        try:
            matches = list(directory.glob(pattern))
            found_files.extend(matches)
        except:
            continue
    
    # Remove duplicates
    return list(set(found_files))