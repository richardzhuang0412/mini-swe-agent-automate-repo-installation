"""
Main parser orchestrator that coordinates all parsing strategies.

This implements the orchestration algorithm described in log_parser/gpt_tips.md:
1. Try structured format parsing first
2. Fall back to line-pattern parsing
3. Use per-file isolation if needed
4. Return consistent unified schema
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from ..schemas.output import TestResults, OverallResult, ParserMeta, TestFramework, calculate_overall_status
from ..core.detector import TestRunnerDetector, RunnerDetection
from ..core.harness import TestHarness, TestExecutionResult
from ..adapters.junit_xml import JUnitXMLParser, find_junit_xml_files
from ..adapters.jest_json import JestJSONParser, find_jest_json_files
from ..adapters.go_json import GoTestJSONParser, find_go_json_files
from ..adapters.line_patterns import LinePatternParser
from ..utils.text_utils import clean_test_output


class TestLogParser:
    """
    Main test log parser that orchestrates different parsing strategies.
    
    Follows the battle-tested workflow from gpt_tips.md:
    1. Execute tests with harness (capture everything)
    2. Detect test runner
    3. Try structured re-run if feasible
    4. Parse via adapters (structured format first)
    5. Fall back to line patterns if needed
    6. Return unified schema
    """
    
    def __init__(self):
        self.detector = TestRunnerDetector()
        self.harness = TestHarness()
        self.structured_parsers = {
            'junit_xml': JUnitXMLParser(),
            'jest_json': JestJSONParser(),
            'go_json': GoTestJSONParser(),
        }
        self.line_parser = LinePatternParser()
    
    def parse_from_dockerfile(self, dockerfile_path: Path, test_commands_path: Optional[Path] = None) -> TestResults:
        """
        Parse test results by running tests from a Dockerfile setup.
        
        Args:
            dockerfile_path: Path to the Dockerfile
            test_commands_path: Path to test_commands.json (optional)
            
        Returns:
            Unified TestResults
        """
        # Load test commands if available
        test_commands = self._load_test_commands(test_commands_path)
        if not test_commands:
            return TestResults(
                overall=OverallResult(status="error", exit_code=-1),
                meta=ParserMeta(
                    runner="unknown",
                    detected_by=["no_test_commands"],
                    confidence=0.0
                )
            )
        
        # Set up working directory (create temporary container)
        working_dir = self._setup_test_environment(dockerfile_path)
        if not working_dir:
            return TestResults(
                overall=OverallResult(status="error", exit_code=-1),
                meta=ParserMeta(
                    runner="unknown", 
                    detected_by=["docker_setup_failed"],
                    confidence=0.0
                )
            )
        
        try:
            return self._run_and_parse_tests(test_commands, working_dir)
        finally:
            # Clean up temporary environment
            self._cleanup_test_environment(working_dir)
    
    def parse_from_output(self, test_output: str, test_command: Optional[str] = None, working_dir: Optional[Path] = None) -> TestResults:
        """
        Parse test results from raw test output.
        
        Args:
            test_output: Raw test output text
            test_command: The command that was executed (for detection hints)
            working_dir: Working directory to search for artifacts
            
        Returns:
            Unified TestResults
        """
        # Clean the output
        cleaned_output = clean_test_output(test_output)
        
        # Try to detect the runner
        detections = []
        
        if test_command:
            command_detection = self.detector.detect_from_command(test_command)
            if command_detection:
                detections.append(command_detection)
        
        if working_dir:
            dir_detections = self.detector.detect_from_directory(working_dir)
            detections.extend(dir_detections)
        
        output_detections = self.detector.detect_from_output(cleaned_output)
        detections.extend(output_detections)
        
        # Combine and get best detection
        combined_detections = self.detector.combine_detections(detections)
        best_detection = combined_detections[0] if combined_detections else None
        
        # Try structured parsing first
        if working_dir:
            structured_result = self._try_structured_parsing(working_dir)
            if structured_result and structured_result.tests:
                # Update metadata with detection info
                if best_detection:
                    structured_result.meta.detected_by.extend(best_detection.detected_by)
                return structured_result
        
        # Fall back to line pattern parsing
        if best_detection:
            line_result = self.line_parser.parse_output(cleaned_output, best_detection.runner)
            if line_result:
                return line_result
        
        # Try line parsing without detection hint
        line_result = self.line_parser.parse_output(cleaned_output)
        if line_result:
            return line_result
        
        # Last resort - return minimal result
        return TestResults(
            overall=OverallResult(status="error", exit_code=1),
            meta=ParserMeta(
                runner="unknown",
                detected_by=["parsing_failed"],
                confidence=0.0,
                fallback_used=True
            )
        )
    
    def _run_and_parse_tests(self, test_commands: Dict[str, Any], working_dir: Path) -> TestResults:
        """Run tests and parse the results using the full orchestration strategy"""
        base_command = test_commands.get('test_command', '')
        structured_flags = test_commands.get('structured_output_flags', {})
        env_vars = test_commands.get('env_vars', {})
        
        if not base_command:
            return TestResults(
                overall=OverallResult(status="error", exit_code=-1),
                meta=ParserMeta(runner="unknown", detected_by=["no_test_command"], confidence=0.0)
            )
        
        # Step 1: Run base command and capture output
        base_result = self.harness.execute_test_command(base_command, str(working_dir), env_vars)
        
        # Step 2: Try structured re-runs if base run doesn't have artifacts
        structured_results = []
        if structured_flags:
            structured_results = self.harness.execute_test_with_structured_flags(
                base_command, str(working_dir), structured_flags, env_vars
            )
        
        # Step 3: Try to parse structured artifacts first
        all_results = [base_result] + structured_results
        for result in all_results:
            structured_parsed = self._try_structured_parsing(working_dir)
            if structured_parsed and structured_parsed.tests:
                # Update with execution info
                structured_parsed.overall.exit_code = result.exit_code
                return structured_parsed
        
        # Step 4: Fall back to line pattern parsing
        # Try the most recent result first (usually has best flags)
        for result in reversed(all_results):
            if result.combined_output.strip():
                line_result = self.line_parser.parse_output(result.combined_output, None)
                if line_result and line_result.tests:
                    # Update exit code from actual execution
                    line_result.overall.exit_code = result.exit_code
                    return line_result
        
        # Step 5: Return basic result based on exit code
        exit_code = base_result.exit_code
        status = "pass" if exit_code == 0 else "fail"
        
        return TestResults(
            overall=OverallResult(status=status, exit_code=exit_code),
            meta=ParserMeta(
                runner=test_commands.get('test_framework', 'unknown'),
                detected_by=["exit_code_only"],
                confidence=0.3,
                fallback_used=True
            )
        )
    
    def _try_structured_parsing(self, working_dir: Path) -> Optional[TestResults]:
        """Try to find and parse structured output files"""
        
        # Try JUnit XML files
        junit_files = find_junit_xml_files(working_dir)
        if junit_files:
            for xml_file in junit_files:
                result = self.structured_parsers['junit_xml'].parse_file(xml_file)
                if result and result.tests:
                    return result
        
        # Try Jest JSON files
        jest_files = find_jest_json_files(working_dir)
        if jest_files:
            for json_file in jest_files:
                result = self.structured_parsers['jest_json'].parse_file(json_file)
                if result and result.tests:
                    return result
        
        # Try Go JSON files
        go_files = find_go_json_files(working_dir)
        if go_files:
            for json_file in go_files:
                result = self.structured_parsers['go_json'].parse_file(json_file)
                if result and result.tests:
                    return result
        
        return None
    
    def _load_test_commands(self, test_commands_path: Optional[Path]) -> Optional[Dict[str, Any]]:
        """Load test commands from JSON file"""
        if not test_commands_path or not test_commands_path.exists():
            return None
        
        try:
            with open(test_commands_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    def _setup_test_environment(self, dockerfile_path: Path) -> Optional[Path]:
        """
        Set up test environment from Dockerfile.
        
        This would typically involve:
        1. Building the Docker image
        2. Creating a container
        3. Setting up volume mounts
        
        For now, we'll return the directory containing the Dockerfile
        as a placeholder implementation.
        """
        if not dockerfile_path.exists():
            return None
        
        # TODO: Implement actual Docker container setup
        # For now, return the parent directory
        return dockerfile_path.parent
    
    def _cleanup_test_environment(self, working_dir: Optional[Path]):
        """Clean up test environment"""
        # TODO: Implement actual Docker cleanup
        pass
    
    def isolate_and_parse_by_file(self, working_dir: Path, detected_runner: Optional[RunnerDetection]) -> TestResults:
        """
        Per-file isolation probe when global parsing fails.
        
        This runs tests file-by-file to get better granularity when
        the global test run output is too opaque.
        """
        if not detected_runner:
            return TestResults(
                overall=OverallResult(status="error", exit_code=-1),
                meta=ParserMeta(runner="unknown", detected_by=["no_detection"], confidence=0.0)
            )
        
        # Find test files based on the detected language/framework
        test_files = self._discover_test_files(working_dir, detected_runner)
        
        if not test_files:
            return TestResults(
                overall=OverallResult(status="error", exit_code=-1),
                meta=ParserMeta(
                    runner=detected_runner.runner.value,
                    detected_by=["no_test_files"], 
                    confidence=0.0
                )
            )
        
        all_tests = {}
        failed_files = 0
        
        # Run each test file separately
        for test_file in test_files[:10]:  # Limit to avoid explosion
            file_command = self._build_file_command(detected_runner, test_file)
            if not file_command:
                continue
            
            try:
                result = self.harness.execute_test_command(file_command, str(working_dir))
                file_parsed = self.line_parser.parse_output(result.combined_output, detected_runner.runner)
                
                if file_parsed and file_parsed.tests:
                    all_tests.update(file_parsed.tests)
                elif result.exit_code != 0:
                    failed_files += 1
                    
            except Exception:
                failed_files += 1
                continue
        
        # Build overall result
        exit_code = 1 if failed_files > 0 else 0
        overall_status = calculate_overall_status(all_tests, exit_code)
        
        total_tests = len(all_tests)
        passed = sum(1 for t in all_tests.values() if t.status == 'pass')
        failed = sum(1 for t in all_tests.values() if t.status == 'fail')
        skipped = sum(1 for t in all_tests.values() if t.status == 'skip')
        errors = sum(1 for t in all_tests.values() if t.status == 'error') + failed_files
        
        return TestResults(
            overall=OverallResult(
                status=overall_status,
                exit_code=exit_code,
                total_tests=total_tests,
                passed=passed,
                failed=failed,
                skipped=skipped,
                errors=errors
            ),
            tests=all_tests,
            meta=ParserMeta(
                runner=detected_runner.runner.value,
                detected_by=detected_runner.detected_by + ["per_file_isolation"],
                confidence=detected_runner.confidence * 0.8,  # Lower confidence for isolation
                fallback_used=True
            )
        )
    
    def _discover_test_files(self, working_dir: Path, detection: RunnerDetection) -> List[Path]:
        """Discover test files based on the detected framework"""
        patterns = {
            TestFramework.PYTEST: ["tests/**/test_*.py", "**/test_*.py", "**/*_test.py"],
            TestFramework.JEST: ["**/*.test.{js,ts,jsx,tsx}", "**/*.spec.{js,ts,jsx,tsx}", "__tests__/**/*"],
            TestFramework.MOCHA: ["test/**/*.{js,ts}", "tests/**/*.{js,ts}"],
            TestFramework.GO_TEST: ["**/*_test.go"],
            TestFramework.CARGO: ["tests/**/*.rs", "src/**/*test*.rs"]
        }
        
        framework_patterns = patterns.get(detection.runner, [])
        test_files = []
        
        for pattern in framework_patterns:
            try:
                matches = list(working_dir.glob(pattern))
                test_files.extend(matches)
            except:
                continue
        
        # Remove duplicates and limit
        return list(set(test_files))[:20]  # Reasonable limit
    
    def _build_file_command(self, detection: RunnerDetection, test_file: Path) -> Optional[str]:
        """Build a command to run a specific test file"""
        framework_commands = {
            TestFramework.PYTEST: f"pytest -q {test_file}",
            TestFramework.JEST: f"jest {test_file}",
            TestFramework.MOCHA: f"mocha {test_file}",
            TestFramework.GO_TEST: f"go test -v {test_file.parent}",  # Go tests by package
            TestFramework.CARGO: f"cargo test --test {test_file.stem}"
        }
        
        return framework_commands.get(detection.runner)