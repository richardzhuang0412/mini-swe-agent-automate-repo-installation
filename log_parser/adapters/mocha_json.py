"""
Mocha JSON parser adapter.

Parses Mocha JSON output format (mocha --reporter json).
"""

import json
from pathlib import Path
from typing import Dict, Optional, Any
from ..schemas.output import TestResults, TestCase, OverallResult, ParserMeta, calculate_overall_status
from ..utils.text_utils import create_stable_test_id, truncate_message


class MochaJSONParser:
    """Parser for Mocha JSON format test results"""
    
    def parse_file(self, json_path: Path) -> Optional[TestResults]:
        """
        Parse a Mocha JSON file and return unified test results.
        
        Args:
            json_path: Path to the Mocha JSON file
            
        Returns:
            TestResults or None if parsing fails
        """
        if not json_path.exists():
            return None
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self._parse_content(content, str(json_path))
        except (json.JSONDecodeError, IOError):
            return None
    
    def parse_string(self, json_content: str) -> Optional[TestResults]:
        """
        Parse Mocha JSON from a string.
        
        Args:
            json_content: JSON content as string
            
        Returns:
            TestResults or None if parsing fails
        """
        return self._parse_content(json_content, "json_content")
    
    def _parse_content(self, content: str, source: str) -> Optional[TestResults]:
        """Parse Mocha JSON content, handling mixed output"""
        # Mocha JSON might be mixed with other output (like npm output)
        # Try to find and extract the JSON part
        
        # Try to find JSON in the content
        # Look for the start of JSON object
        json_start_pos = content.find('{\n  "stats"')
        if json_start_pos == -1:
            json_start_pos = content.find('{"stats"')
        if json_start_pos == -1:
            return None
        
        # Find the end by counting braces
        brace_count = 0
        json_end_pos = len(content)
        
        for i in range(json_start_pos, len(content)):
            char = content[i]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end_pos = i + 1
                    break
        
        # Extract JSON content
        json_text = content[json_start_pos:json_end_pos]
        
        try:
            data = json.loads(json_text)
            return self._parse_mocha_data(data, source)
        except json.JSONDecodeError:
            return None
    
    def _parse_mocha_data(self, data: Dict[str, Any], source: str) -> TestResults:
        """Parse Mocha JSON data structure"""
        tests = {}
        
        # Extract overall statistics
        stats = data.get('stats', {})
        total_tests = stats.get('tests', 0)
        passed_tests = stats.get('passes', 0)
        failed_tests = stats.get('failures', 0)
        pending_tests = stats.get('pending', 0)
        
        # Calculate duration - Mocha reports in milliseconds
        duration_ms = stats.get('duration', 0)
        duration_s = duration_ms / 1000.0 if duration_ms > 0 else None
        
        # Parse individual test results
        test_results = data.get('tests', [])
        for test_result in test_results:
            test_case = self._parse_test_result(test_result)
            if test_case:
                test_id, test_case_obj = test_case
                tests[test_id] = test_case_obj
        
        # Parse failures for additional error information
        failures = data.get('failures', [])
        for failure in failures:
            self._add_failure_info(failure, tests)
        
        # Determine overall status
        exit_code = 1 if failed_tests > 0 else 0
        overall_status = calculate_overall_status(tests, exit_code)
        
        overall = OverallResult(
            status=overall_status,
            exit_code=exit_code,
            duration_s=duration_s,
            total_tests=total_tests,
            passed=passed_tests,
            failed=failed_tests,
            skipped=pending_tests,
            errors=0  # Mocha doesn't typically distinguish errors from failures
        )
        
        meta = ParserMeta(
            runner="mocha",
            detected_by=[source],
            confidence=1.0,
            structured_format=True
        )
        
        return TestResults(
            overall=overall,
            tests=tests,
            meta=meta
        )
    
    def _parse_test_result(self, test_result: Dict[str, Any]) -> Optional[tuple]:
        """Parse a single test result from Mocha JSON"""
        title = test_result.get('title', '')
        full_title = test_result.get('fullTitle', title)
        file_path = test_result.get('file', '')
        
        # Clean up file path (remove /app prefix if present)
        if file_path.startswith('/app/'):
            file_path = file_path[5:]
        
        # Parse duration (Mocha reports in milliseconds)
        duration = None
        duration_ms = test_result.get('duration')
        if duration_ms is not None:
            duration = duration_ms / 1000.0
        
        # Determine status - Mocha JSON doesn't always have explicit state
        # Infer from error and other fields
        err = test_result.get('err', {})
        state = test_result.get('state', None)
        
        if state:
            status_map = {
                'passed': 'pass',
                'failed': 'fail',
                'pending': 'skip'
            }
            status = status_map.get(state, 'error')
        else:
            # Infer status from error presence and other indicators
            if err and (err.get('message') or err.get('stack') or str(err) != '{}'):
                status = 'fail'
            elif test_result.get('pending', False):
                status = 'skip'
            else:
                status = 'pass'  # Default to pass if no error
        
        # Extract suite information from fullTitle
        suite_parts = full_title.split(title)
        suite_name = suite_parts[0].strip() if len(suite_parts) > 1 else None
        
        # Create test ID
        test_id = create_stable_test_id(file_path, suite_name, title)
        
        # Extract error information if failed
        message = None
        if status == 'fail':
            err = test_result.get('err', {})
            if err:
                message = err.get('message', '')
                if not message:
                    message = str(err)
                message = truncate_message(message)
        
        test_case = TestCase(
            status=status,
            file=file_path if file_path else None,
            line=None,  # Not typically available in Mocha JSON
            duration_s=duration,
            message=message,
            stdout=None,  # Not typically included in Mocha JSON
            stderr=None
        )
        
        return test_id, test_case
    
    def _add_failure_info(self, failure: Dict[str, Any], tests: Dict[str, TestCase]):
        """Add detailed failure information to tests"""
        title = failure.get('title', '')
        full_title = failure.get('fullTitle', title)
        
        # Find the corresponding test case
        for test_id, test_case in tests.items():
            if title in test_id or full_title in test_id:
                # Update with detailed error info
                err = failure.get('err', {})
                if err:
                    message = err.get('message', '')
                    stack = err.get('stack', '')
                    
                    if message and stack:
                        combined_message = f"{message}\n{stack}"
                    elif stack:
                        combined_message = stack
                    elif message:
                        combined_message = message
                    else:
                        combined_message = str(err)
                    
                    test_case.message = truncate_message(combined_message)
                break


def find_mocha_json_files(directory: Path) -> list[Path]:
    """Find Mocha JSON result files in a directory tree"""
    patterns = [
        "mocha-results*.json",
        "**/results/mocha*.json",
        "**/test-results/mocha*.json"
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