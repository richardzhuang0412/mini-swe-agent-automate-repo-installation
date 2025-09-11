"""
JUnit XML parser adapter.

Parses JUnit XML format which is supported by many frameworks including:
- pytest (--junitxml)
- Maven Surefire
- Gradle
- phpunit
- And many others
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional, List
from ..schemas.output import TestResults, TestCase, OverallResult, ParserMeta, calculate_overall_status
from ..utils.text_utils import create_stable_test_id, parse_duration, truncate_message


class JUnitXMLParser:
    """Parser for JUnit XML format test results"""
    
    def parse_file(self, xml_path: Path) -> Optional[TestResults]:
        """
        Parse a JUnit XML file and return unified test results.
        
        Args:
            xml_path: Path to the JUnit XML file
            
        Returns:
            TestResults or None if parsing fails
        """
        if not xml_path.exists():
            return None
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            return self._parse_xml_root(root, xml_path)
        except ET.ParseError as e:
            # Return error result if XML is malformed
            return TestResults(
                overall=OverallResult(status="error", exit_code=-1),
                meta=ParserMeta(
                    runner="junit-xml",
                    detected_by=[f"xml_parse_error: {str(e)}"],
                    confidence=0.0,
                    structured_format=True
                )
            )
        except Exception as e:
            return None
    
    def parse_string(self, xml_content: str) -> Optional[TestResults]:
        """
        Parse JUnit XML from a string.
        
        Args:
            xml_content: XML content as string
            
        Returns:
            TestResults or None if parsing fails
        """
        try:
            root = ET.fromstring(xml_content)
            return self._parse_xml_root(root)
        except ET.ParseError:
            return None
        except Exception:
            return None
    
    def _parse_xml_root(self, root: ET.Element, source_file: Optional[Path] = None) -> TestResults:
        """Parse the root XML element and extract test results"""
        tests = {}
        total_duration = 0.0
        total_tests = 0
        total_failures = 0
        total_errors = 0
        total_skipped = 0
        
        # Handle both single testsuite and testsuites with multiple suites
        if root.tag == 'testsuites':
            testsuites = root.findall('testsuite')
        elif root.tag == 'testsuite':
            testsuites = [root]
        else:
            # Unknown root element
            return TestResults(
                overall=OverallResult(status="error", exit_code=-1),
                meta=ParserMeta(
                    runner="junit-xml", 
                    detected_by=["unknown_root_element"],
                    confidence=0.0,
                    structured_format=True
                )
            )
        
        for testsuite in testsuites:
            suite_results = self._parse_testsuite(testsuite)
            tests.update(suite_results["tests"])
            
            # Aggregate statistics
            total_duration += suite_results["duration"]
            total_tests += suite_results["tests_count"]
            total_failures += suite_results["failures"]
            total_errors += suite_results["errors"] 
            total_skipped += suite_results["skipped"]
        
        # Calculate overall result
        passed = total_tests - total_failures - total_errors - total_skipped
        exit_code = 1 if (total_failures + total_errors) > 0 else 0
        overall_status = calculate_overall_status(tests, exit_code)
        
        overall = OverallResult(
            status=overall_status,
            exit_code=exit_code,
            duration_s=total_duration if total_duration > 0 else None,
            total_tests=total_tests,
            passed=passed,
            failed=total_failures,
            skipped=total_skipped,
            errors=total_errors
        )
        
        meta = ParserMeta(
            runner="junit-xml",
            detected_by=[str(source_file)] if source_file else ["xml_content"],
            confidence=1.0,
            structured_format=True
        )
        
        return TestResults(
            overall=overall,
            tests=tests,
            meta=meta
        )
    
    def _parse_testsuite(self, testsuite: ET.Element) -> Dict:
        """Parse a single testsuite element"""
        suite_name = testsuite.get('name', '')
        suite_file = testsuite.get('file', None)
        
        tests = {}
        suite_duration = 0.0
        failures = 0
        errors = 0
        skipped = 0
        tests_count = 0
        
        # Parse testsuite attributes
        try:
            suite_duration = float(testsuite.get('time', '0'))
        except (ValueError, TypeError):
            suite_duration = 0.0
        
        try:
            failures = int(testsuite.get('failures', '0'))
        except (ValueError, TypeError):
            failures = 0
        
        try:
            errors = int(testsuite.get('errors', '0'))
        except (ValueError, TypeError):
            errors = 0
        
        try:
            skipped = int(testsuite.get('skipped', '0'))
        except (ValueError, TypeError):
            skipped = 0
        
        # Parse individual testcases
        for testcase in testsuite.findall('testcase'):
            test_result = self._parse_testcase(testcase, suite_name, suite_file)
            if test_result:
                test_id, test_case = test_result
                tests[test_id] = test_case
                tests_count += 1
        
        return {
            "tests": tests,
            "duration": suite_duration,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "tests_count": tests_count
        }
    
    def _parse_testcase(self, testcase: ET.Element, suite_name: str, suite_file: Optional[str]) -> Optional[tuple]:
        """Parse a single testcase element"""
        test_name = testcase.get('name', '')
        class_name = testcase.get('classname', '')
        test_file = testcase.get('file') or suite_file
        
        # Create test ID
        test_id = create_stable_test_id(test_file, class_name or suite_name, test_name)
        
        # Parse duration
        duration = None
        time_attr = testcase.get('time')
        if time_attr:
            try:
                duration = float(time_attr)
            except (ValueError, TypeError):
                duration = None
        
        # Parse line number
        line = None
        line_attr = testcase.get('line')
        if line_attr:
            try:
                line = int(line_attr)
            except (ValueError, TypeError):
                line = None
        
        # Determine status and extract failure/error info
        status = "pass"
        message = None
        stdout = None
        stderr = None
        
        # Check for failure
        failure_elem = testcase.find('failure')
        if failure_elem is not None:
            status = "fail"
            message = failure_elem.get('message', '')
            if failure_elem.text:
                message += f"\n{failure_elem.text}"
            message = truncate_message(message)
        
        # Check for error
        error_elem = testcase.find('error')
        if error_elem is not None:
            status = "error"
            message = error_elem.get('message', '')
            if error_elem.text:
                message += f"\n{error_elem.text}"
            message = truncate_message(message)
        
        # Check for skipped
        skipped_elem = testcase.find('skipped')
        if skipped_elem is not None:
            status = "skip"
            message = skipped_elem.get('message', '')
            if skipped_elem.text:
                message += f"\n{skipped_elem.text}"
            message = truncate_message(message)
        
        # Extract stdout/stderr if present
        system_out = testcase.find('system-out')
        if system_out is not None and system_out.text:
            stdout = system_out.text.strip()
        
        system_err = testcase.find('system-err')
        if system_err is not None and system_err.text:
            stderr = system_err.text.strip()
        
        test_case = TestCase(
            status=status,
            file=test_file,
            line=line,
            duration_s=duration,
            message=message,
            stdout=stdout,
            stderr=stderr
        )
        
        return test_id, test_case


def find_junit_xml_files(directory: Path) -> List[Path]:
    """Find JUnit XML files in a directory tree"""
    patterns = [
        "junit*.xml",
        "TEST-*.xml", 
        "**/test-results/**/*.xml",
        "**/target/surefire-reports/*.xml",
        "**/build/test-results/**/*.xml",
        "**/Testing/*/Test.xml",
        "**/results/*.xml"
    ]
    
    found_files = []
    for pattern in patterns:
        try:
            matches = list(directory.glob(pattern))
            found_files.extend(matches)
        except:
            continue
    
    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for file_path in found_files:
        if file_path not in seen:
            seen.add(file_path)
            unique_files.append(file_path)
    
    return unique_files