"""
Line-pattern fallback parsers for plain text test output.

These parsers use regex patterns to extract test results from unstructured
plain text output when no structured format is available.
"""

import re
from typing import Dict, List, Optional, Tuple, NamedTuple
from ..schemas.output import TestResults, TestCase, OverallResult, ParserMeta, TestFramework, calculate_overall_status
from ..utils.text_utils import create_stable_test_id, parse_duration, truncate_message


class PatternMatch(NamedTuple):
    """Represents a pattern match with its score"""
    framework: TestFramework
    score: float
    evidence: List[str]


class TestCaseMatch(NamedTuple):
    """Represents a matched test case from pattern parsing"""
    test_id: str
    status: str
    duration_s: Optional[float] = None
    message: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None


class LinePatternParser:
    """
    Fallback parser that uses regex patterns to extract test results from plain text output.
    
    This is used when no structured output format is available.
    """
    
    def __init__(self):
        self.signatures = self._init_signatures()
    
    def parse_output(self, output: str, detected_runner: Optional[TestFramework] = None) -> Optional[TestResults]:
        """
        Parse test output using line patterns.
        
        Args:
            output: Raw test output text
            detected_runner: Hint about which runner to prefer (optional)
            
        Returns:
            TestResults or None if no patterns match
        """
        if not output.strip():
            return None
        
        # Find the best matching signature
        best_match = self._find_best_signature(output, detected_runner)
        
        if not best_match or best_match.score < 0.3:  # Minimum confidence threshold
            return None
        
        # Parse using the best matching signature
        return self._parse_with_signature(output, best_match)
    
    def _find_best_signature(self, output: str, hint_runner: Optional[TestFramework] = None) -> Optional[PatternMatch]:
        """Find the best matching signature for the output"""
        matches = []
        
        for framework, signature in self.signatures.items():
            score, evidence = signature.score(output)
            
            # Boost score if this matches the detected runner
            if hint_runner and framework == hint_runner:
                score *= 1.5
            
            if score > 0:
                matches.append(PatternMatch(framework, score, evidence))
        
        if not matches:
            return None
        
        # Return the highest scoring match
        matches.sort(key=lambda x: x.score, reverse=True)
        return matches[0]
    
    def _parse_with_signature(self, output: str, match: PatternMatch) -> TestResults:
        """Parse output using a specific signature"""
        signature = self.signatures[match.framework]
        test_cases = signature.parse_test_cases(output)
        summary = signature.parse_summary(output)
        
        # Convert test cases to our format
        tests = {}
        for case in test_cases:
            tests[case.test_id] = TestCase(
                status=case.status,
                file=case.file,
                line=case.line,
                duration_s=case.duration_s,
                message=case.message,
                stdout=None,
                stderr=None
            )
        
        # Use summary stats if available, otherwise calculate from individual tests
        if summary:
            total_tests = summary.get('total', len(tests))
            passed = summary.get('passed', 0)
            failed = summary.get('failed', 0)
            skipped = summary.get('skipped', 0)
            errors = summary.get('errors', 0)
            exit_code = 1 if (failed + errors) > 0 else 0
        else:
            total_tests = len(tests)
            passed = sum(1 for t in tests.values() if t.status == 'pass')
            failed = sum(1 for t in tests.values() if t.status == 'fail')
            skipped = sum(1 for t in tests.values() if t.status == 'skip')
            errors = sum(1 for t in tests.values() if t.status == 'error')
            exit_code = 1 if (failed + errors) > 0 else 0
        
        overall_status = calculate_overall_status(tests, exit_code)
        
        overall = OverallResult(
            status=overall_status,
            exit_code=exit_code,
            duration_s=None,  # Usually not available in plain text
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors
        )
        
        meta = ParserMeta(
            runner=match.framework.value,
            detected_by=match.evidence,
            confidence=match.score,
            structured_format=False,
            fallback_used=True
        )
        
        return TestResults(
            overall=overall,
            tests=tests,
            meta=meta
        )
    
    def _init_signatures(self) -> Dict[TestFramework, 'PatternSignature']:
        """Initialize pattern signatures for different frameworks"""
        return {
            TestFramework.PYTEST: PytestSignature(),
            TestFramework.JEST: JestSignature(),
            TestFramework.MOCHA: MochaSignature(),
            TestFramework.GO_TEST: GoTestSignature(),
            TestFramework.CARGO: CargoSignature(),
            TestFramework.JUNIT: JUnitSignature(),
            TestFramework.PHPUNIT: PHPUnitSignature(),
            TestFramework.RSPEC: RSpecSignature(),
        }


class PatternSignature:
    """Base class for framework-specific pattern signatures"""
    
    def score(self, output: str) -> Tuple[float, List[str]]:
        """
        Score how well this signature matches the output.
        
        Returns:
            (score, evidence) where score is 0.0-1.0 and evidence is list of matched patterns
        """
        raise NotImplementedError
    
    def parse_test_cases(self, output: str) -> List[TestCaseMatch]:
        """Extract individual test cases from output"""
        raise NotImplementedError
    
    def parse_summary(self, output: str) -> Optional[Dict[str, int]]:
        """Extract summary statistics from output"""
        return None


class PytestSignature(PatternSignature):
    """Pattern signature for pytest output"""
    
    def __init__(self):
        self.header_patterns = [
            r'=+ test session starts =+',
            r'=+.*pytest.*=+',
            r'collected \d+ items?'
        ]
        
        self.case_patterns = [
            r'^([^:]+::[^:]+::[^\s]+)\s+(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)(?:\s+\[([^\]]+)\])?',
            r'^([^\s]+)\s+(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)',
        ]
        
        self.summary_patterns = [
            r'=+.*(\d+)\s+failed.*(\d+)\s+passed.*in\s+([\d.]+)s',
            r'=+.*(\d+)\s+passed.*in\s+([\d.]+)s',
            r'=+.*(\d+)\s+error.*(\d+)\s+passed.*in\s+([\d.]+)s',
        ]
    
    def score(self, output: str) -> Tuple[float, List[str]]:
        score = 0.0
        evidence = []
        
        for pattern in self.header_patterns:
            if re.search(pattern, output, re.MULTILINE | re.IGNORECASE):
                score += 0.3
                evidence.append(f"header: {pattern}")
        
        # Look for case-level patterns
        lines = output.split('\n')
        case_matches = 0
        for line in lines:
            for pattern in self.case_patterns:
                if re.search(pattern, line):
                    case_matches += 1
                    break
        
        if case_matches > 0:
            score += min(case_matches * 0.1, 0.4)
            evidence.append(f"test_cases: {case_matches}")
        
        # Look for summary patterns
        for pattern in self.summary_patterns:
            if re.search(pattern, output, re.MULTILINE | re.IGNORECASE):
                score += 0.3
                evidence.append(f"summary: {pattern}")
                break
        
        return min(score, 1.0), evidence
    
    def parse_test_cases(self, output: str) -> List[TestCaseMatch]:
        cases = []
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            for pattern in self.case_patterns:
                match = re.search(pattern, line)
                if match:
                    groups = match.groups()
                    if len(groups) >= 2:
                        test_full_name = groups[0]
                        status = groups[1]
                        
                        # For pytest, test_full_name is like "test_math.py::test_addition"
                        parts = test_full_name.split('::')
                        if len(parts) >= 2:
                            file_path = parts[0]
                            if len(parts) == 3:
                                class_name = parts[1]
                                test_name = parts[2]
                            else:
                                class_name = None
                                test_name = parts[1]
                        else:
                            file_path = None
                            class_name = None
                            test_name = test_full_name
                        
                        # Normalize status
                        status_map = {
                            'PASSED': 'pass',
                            'FAILED': 'fail', 
                            'SKIPPED': 'skip',
                            'ERROR': 'error',
                            'XFAIL': 'xfail',
                            'XPASS': 'xpass'
                        }
                        
                        test_id = create_stable_test_id(file_path, class_name, test_name)
                        cases.append(TestCaseMatch(
                            test_id=test_id,
                            status=status_map.get(status.upper(), 'error'),
                            file=file_path
                        ))
                        break
        
        return cases


class JestSignature(PatternSignature):
    """Pattern signature for Jest output"""
    
    def __init__(self):
        self.header_patterns = [
            r'PASS|FAIL.*\.test\.(js|ts|jsx|tsx)',
            r'Test Suites:.*\d+.*passed'
        ]
        
        self.case_patterns = [
            r'^\s*(✓|✗|○)\s*(.*?)\s*\((\d+)ms\)',
            r'^\s*(PASS|FAIL)\s*(.*)'
        ]
        
        self.summary_patterns = [
            r'Test Suites:.*(\d+)\s+passed.*(\d+)\s+total',
            r'Tests:\s+(\d+)\s+failed.*(\d+)\s+passed.*(\d+)\s+total'
        ]
    
    def score(self, output: str) -> Tuple[float, List[str]]:
        score = 0.0
        evidence = []
        
        for pattern in self.header_patterns:
            if re.search(pattern, output, re.MULTILINE | re.IGNORECASE):
                score += 0.4
                evidence.append(f"header: {pattern}")
        
        for pattern in self.summary_patterns:
            if re.search(pattern, output, re.MULTILINE | re.IGNORECASE):
                score += 0.4
                evidence.append(f"summary: {pattern}")
        
        return min(score, 1.0), evidence
    
    def parse_test_cases(self, output: str) -> List[TestCaseMatch]:
        cases = []
        lines = output.split('\n')
        current_file = None
        
        for line in lines:
            # Track current file
            file_match = re.search(r'(PASS|FAIL)\s+(.+\.test\.(js|ts|jsx|tsx))', line)
            if file_match:
                current_file = file_match.group(2)
                continue
            
            # Parse test cases
            for pattern in self.case_patterns:
                match = re.search(pattern, line.strip())
                if match:
                    groups = match.groups()
                    if len(groups) >= 2:
                        symbol = groups[0]
                        test_name = groups[1]
                        duration_ms = int(groups[2]) if len(groups) > 2 and groups[2].isdigit() else None
                        
                        status_map = {
                            '✓': 'pass',
                            '✗': 'fail',
                            '○': 'skip',
                            'PASS': 'pass',
                            'FAIL': 'fail'
                        }
                        
                        status = status_map.get(symbol, 'error')
                        duration_s = duration_ms / 1000.0 if duration_ms else None
                        
                        test_id = create_stable_test_id(current_file, None, test_name)
                        cases.append(TestCaseMatch(
                            test_id=test_id,
                            status=status,
                            duration_s=duration_s,
                            file=current_file
                        ))
                        break
        
        return cases


class GoTestSignature(PatternSignature):
    """Pattern signature for Go test output"""
    
    def __init__(self):
        self.patterns = [
            r'=== RUN\s+(\S+)',
            r'--- (PASS|FAIL):\s+(\S+)\s+\((\d+\.\d+)s\)',
            r'(ok|FAIL)\s+(\S+)\s+(\d+\.\d+)s',
        ]
    
    def score(self, output: str) -> Tuple[float, List[str]]:
        score = 0.0
        evidence = []
        
        for pattern in self.patterns:
            matches = re.findall(pattern, output, re.MULTILINE)
            if matches:
                score += min(len(matches) * 0.2, 0.6)
                evidence.append(f"go_pattern: {len(matches)} matches")
        
        return min(score, 1.0), evidence
    
    def parse_test_cases(self, output: str) -> List[TestCaseMatch]:
        cases = []
        
        # Parse individual test results
        pattern = r'--- (PASS|FAIL):\s+(\S+)\s+\((\d+\.\d+)s\)'
        for match in re.finditer(pattern, output, re.MULTILINE):
            status_str, test_name, duration_str = match.groups()
            status = 'pass' if status_str == 'PASS' else 'fail'
            duration_s = float(duration_str)
            
            test_id = create_stable_test_id(None, None, test_name)
            cases.append(TestCaseMatch(
                test_id=test_id,
                status=status,
                duration_s=duration_s
            ))
        
        return cases


class CargoSignature(PatternSignature):
    """Pattern signature for Cargo test output"""
    
    def __init__(self):
        self.patterns = [
            r'running \d+ tests?',
            r'test result: (ok|FAILED)\. (\d+) passed; (\d+) failed',
            r'test \S+ \.\.\. (ok|FAILED|ignored)'
        ]
    
    def score(self, output: str) -> Tuple[float, List[str]]:
        score = 0.0
        evidence = []
        
        for pattern in self.patterns:
            if re.search(pattern, output, re.MULTILINE | re.IGNORECASE):
                score += 0.4
                evidence.append(f"cargo_pattern: {pattern}")
        
        return min(score, 1.0), evidence
    
    def parse_test_cases(self, output: str) -> List[TestCaseMatch]:
        cases = []
        
        pattern = r'test (\S+) \.\.\. (ok|FAILED|ignored)'
        for match in re.finditer(pattern, output, re.MULTILINE):
            test_name, result = match.groups()
            
            status_map = {
                'ok': 'pass',
                'FAILED': 'fail',
                'ignored': 'skip'
            }
            
            status = status_map.get(result, 'error')
            test_id = create_stable_test_id(None, None, test_name)
            
            cases.append(TestCaseMatch(
                test_id=test_id,
                status=status
            ))
        
        return cases


# Placeholder signatures for other frameworks
class MochaSignature(PatternSignature):
    """Pattern signature for Mocha output (spec reporter)"""
    
    def __init__(self):
        self.header_patterns = [
            r'> mocha',
            r'--reporter spec'
        ]
        
        self.case_patterns = [
            r'^\s*✔\s+(.+?)(?:\s+\((\d+)ms\))?$',  # Passing tests
            r'^\s*\d+\)\s+(.+?)$',  # Failed tests (numbered)
            r'^\s*-\s+(.+?)$'  # Skipped tests
        ]
        
        self.summary_patterns = [
            r'(\d+)\s+passing\s*(?:\(([^)]+)\))?',
            r'(\d+)\s+failing',
            r'(\d+)\s+pending'
        ]
    
    def score(self, output: str) -> Tuple[float, List[str]]:
        score = 0.0
        evidence = []
        
        # Look for Mocha indicators
        if 'passing' in output.lower() and re.search(r'\d+ms', output):
            score += 0.6
            evidence.append("mocha_indicators")
        
        # Look for header patterns
        for pattern in self.header_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                score += 0.3
                evidence.append(f"header: {pattern}")
        
        # Look for summary patterns
        for pattern in self.summary_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                score += 0.4
                evidence.append(f"summary: {pattern}")
                break
        
        return min(score, 1.0), evidence
    
    def parse_test_cases(self, output: str) -> List[TestCaseMatch]:
        cases = []
        lines = output.split('\n')
        current_suite = None
        
        for line in lines:
            line_stripped = line.strip()
            
            # Track current suite/describe block
            if line_stripped and not line_stripped.startswith(('✔', '✓', '×', '1)', '2)', '3)', '4)', '5)', '6)', '7)', '8)', '9)', '-')):
                # This might be a suite/describe name
                if not any(char in line_stripped for char in ['(', ')', 'ms', 'passing', 'failing']):
                    potential_suite = line_stripped
                    if len(potential_suite) < 100:  # Reasonable suite name length
                        current_suite = potential_suite
            
            # Parse individual test cases
            for pattern in self.case_patterns:
                match = re.search(pattern, line)
                if match:
                    test_name = match.group(1).strip()
                    duration_ms = None
                    
                    if len(match.groups()) > 1 and match.group(2):
                        try:
                            duration_ms = int(match.group(2))
                        except ValueError:
                            pass
                    
                    # Determine status based on pattern
                    if pattern.startswith(r'^\s*✔'):
                        status = 'pass'
                    elif pattern.startswith(r'^\s*\d+\)'):
                        status = 'fail'
                    elif pattern.startswith(r'^\s*-'):
                        status = 'skip'
                    else:
                        status = 'error'
                    
                    # Create test ID
                    test_id = create_stable_test_id(None, current_suite, test_name)
                    duration_s = duration_ms / 1000.0 if duration_ms else None
                    
                    cases.append(TestCaseMatch(
                        test_id=test_id,
                        status=status,
                        duration_s=duration_s
                    ))
                    break
        
        return cases
    
    def parse_summary(self, output: str) -> Optional[Dict[str, int]]:
        """Extract summary statistics from Mocha output"""
        summary = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}
        
        # Look for "X passing" pattern
        passing_match = re.search(r'(\d+)\s+passing', output, re.IGNORECASE)
        if passing_match:
            summary['passed'] = int(passing_match.group(1))
            summary['total'] += summary['passed']
        
        # Look for "X failing" pattern
        failing_match = re.search(r'(\d+)\s+failing', output, re.IGNORECASE)
        if failing_match:
            summary['failed'] = int(failing_match.group(1))
            summary['total'] += summary['failed']
        
        # Look for "X pending" pattern
        pending_match = re.search(r'(\d+)\s+pending', output, re.IGNORECASE)
        if pending_match:
            summary['skipped'] = int(pending_match.group(1))
            summary['total'] += summary['skipped']
        
        return summary if summary['total'] > 0 else None


class JUnitSignature(PatternSignature):
    def score(self, output: str) -> Tuple[float, List[str]]:
        if re.search(r'Tests run: \d+', output, re.IGNORECASE):
            return 0.7, ["junit_summary"]
        return 0.0, []
    
    def parse_test_cases(self, output: str) -> List[TestCaseMatch]:
        return []  # TODO: Implement JUnit parsing


class PHPUnitSignature(PatternSignature):
    def score(self, output: str) -> Tuple[float, List[str]]:
        if 'PHPUnit' in output and re.search(r'Tests: \d+', output):
            return 0.8, ["phpunit_header"]
        return 0.0, []
    
    def parse_test_cases(self, output: str) -> List[TestCaseMatch]:
        return []  # TODO: Implement PHPUnit parsing


class RSpecSignature(PatternSignature):
    def score(self, output: str) -> Tuple[float, List[str]]:
        if re.search(r'\d+ examples?, \d+ failures?', output):
            return 0.7, ["rspec_summary"]
        return 0.0, []
    
    def parse_test_cases(self, output: str) -> List[TestCaseMatch]:
        return []  # TODO: Implement RSpec parsing