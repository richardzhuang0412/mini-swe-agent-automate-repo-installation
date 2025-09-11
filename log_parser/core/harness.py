"""
Test execution harness for capturing test output in a parser-friendly format.

This harness runs tests with proper output capture, ANSI stripping, timeout handling,
and environmental setup to encourage machine-readable output.
"""

import subprocess
import os
import tempfile
import time
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# ANSI color code regex for stripping
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


@dataclass
class TestExecutionResult:
    """Result of a test execution"""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    combined_output: str
    duration_s: float
    start_timestamp: float
    end_timestamp: float
    working_dir: str
    env_vars: Dict[str, str]
    raw_stdout: str  # Before ANSI stripping
    raw_stderr: str
    timeout_occurred: bool = False


class TestHarness:
    """
    Test execution harness that captures output in a parser-friendly format.
    
    Features:
    - Strips ANSI color codes for clean parsing
    - Sets CI environment variables to encourage machine-readable output
    - Captures stdout, stderr, and combined output
    - Implements timeout protection
    - Records timing information
    """
    
    def __init__(self, 
                 timeout: int = 300,  # 5 minutes default
                 memory_limit: Optional[int] = None,  # MB
                 line_limit: int = 100000):  # Max lines in output
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.line_limit = line_limit
    
    def execute_test_command(self, 
                           command: str, 
                           working_dir: str, 
                           extra_env: Optional[Dict[str, str]] = None) -> TestExecutionResult:
        """
        Execute a test command with proper output capture and environment setup.
        
        Args:
            command: The test command to execute
            working_dir: Working directory for the command
            extra_env: Additional environment variables
            
        Returns:
            TestExecutionResult with all captured information
        """
        start_time = time.time()
        
        # Set up environment for machine-readable output
        env = os.environ.copy()
        env.update({
            # General CI/automation flags
            'CI': 'true',
            'FORCE_COLOR': '0',
            'NO_COLOR': '1',
            'TERM': 'dumb',
            'TZ': 'UTC',
            'LANG': 'C.UTF-8',
            'LC_ALL': 'C.UTF-8',
            
            # Framework-specific flags for better output
            'PYTEST_ADDOPTS': '-q --tb=short',
            'MOCHA_REPORTER': 'spec',
            'NODE_ENV': 'test',
            'CARGO_TERM_COLOR': 'never',
            'RUST_BACKTRACE': '1',
            'GO_TEST_VERBOSE': 'false',
        })
        
        if extra_env:
            env.update(extra_env)
        
        # Create temporary files for output capture
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.stdout', delete=False) as stdout_file, \
             tempfile.NamedTemporaryFile(mode='w+', suffix='.stderr', delete=False) as stderr_file, \
             tempfile.NamedTemporaryFile(mode='w+', suffix='.combined', delete=False) as combined_file:
            
            stdout_path = stdout_file.name
            stderr_path = stderr_file.name
            combined_path = combined_file.name
        
        timeout_occurred = False
        
        try:
            # Use tee to capture both stdout/stderr separately and combined
            # This bash command captures everything we need
            bash_command = f"""
            set -o pipefail
            exec 3>&1 4>&2
            {{ 
                {command} 2>&1 | tee {combined_path} 
            }} 1>{stdout_path} 2>{stderr_path}
            echo $? > /tmp/exit_code_$$
            """
            
            process = subprocess.run(
                bash_command,
                shell=True,
                cwd=working_dir,
                env=env,
                timeout=self.timeout,
                capture_output=False,  # We're handling output capture manually
                text=True,
                executable='/bin/bash'
            )
            
            exit_code = process.returncode
            
        except subprocess.TimeoutExpired:
            timeout_occurred = True
            exit_code = -1  # Timeout exit code
        
        except Exception as e:
            # If there's any other error, we still want to try to read what we can
            exit_code = -2
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Read captured output
        try:
            with open(stdout_path, 'r', encoding='utf-8', errors='replace') as f:
                raw_stdout = f.read()
        except:
            raw_stdout = ""
        
        try:
            with open(stderr_path, 'r', encoding='utf-8', errors='replace') as f:
                raw_stderr = f.read()
        except:
            raw_stderr = ""
        
        try:
            with open(combined_path, 'r', encoding='utf-8', errors='replace') as f:
                raw_combined = f.read()
        except:
            raw_combined = raw_stdout + raw_stderr
        
        # Clean up temporary files
        for path in [stdout_path, stderr_path, combined_path]:
            try:
                os.unlink(path)
            except:
                pass
        
        # Strip ANSI codes for clean parsing
        clean_stdout = self._strip_ansi(raw_stdout)
        clean_stderr = self._strip_ansi(raw_stderr)
        clean_combined = self._strip_ansi(raw_combined)
        
        # Limit line count if necessary
        clean_stdout = self._limit_lines(clean_stdout)
        clean_stderr = self._limit_lines(clean_stderr)
        clean_combined = self._limit_lines(clean_combined)
        
        return TestExecutionResult(
            command=command,
            exit_code=exit_code,
            stdout=clean_stdout,
            stderr=clean_stderr,
            combined_output=clean_combined,
            duration_s=duration,
            start_timestamp=start_time,
            end_timestamp=end_time,
            working_dir=working_dir,
            env_vars=env,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            timeout_occurred=timeout_occurred
        )
    
    def execute_test_with_structured_flags(self,
                                         base_command: str,
                                         working_dir: str,
                                         structured_flags: Dict[str, str],
                                         extra_env: Optional[Dict[str, str]] = None) -> List[TestExecutionResult]:
        """
        Execute test with various structured output flags to try to get machine-readable results.
        
        Args:
            base_command: Base test command (e.g., "npm test")
            working_dir: Working directory
            structured_flags: Dict of flag_name -> flag_value for structured output
            extra_env: Additional environment variables
            
        Returns:
            List of TestExecutionResult, one for each flag attempt
        """
        results = []
        
        for flag_name, flag_value in structured_flags.items():
            if not flag_value:
                continue
                
            # Construct command with structured flag
            structured_command = f"{base_command} {flag_value}"
            
            result = self.execute_test_command(
                structured_command,
                working_dir,
                extra_env
            )
            
            # Add metadata about which flag was used
            result.command = f"{result.command} [{flag_name}]"
            results.append(result)
        
        return results
    
    def _strip_ansi(self, text: str) -> str:
        """Strip ANSI escape sequences from text"""
        return ANSI_ESCAPE.sub('', text)
    
    def _limit_lines(self, text: str) -> str:
        """Limit text to maximum number of lines"""
        if not text:
            return text
        
        lines = text.split('\n')
        if len(lines) <= self.line_limit:
            return text
        
        # Keep first half and last half of lines
        keep_lines = self.line_limit
        half = keep_lines // 2
        
        truncated_lines = (
            lines[:half] + 
            [f"... [TRUNCATED {len(lines) - keep_lines} lines] ..."] +
            lines[-half:]
        )
        
        return '\n'.join(truncated_lines)
    
    def find_test_artifacts(self, working_dir: str) -> Dict[str, List[Path]]:
        """
        Search for common test artifact files that might contain structured results.
        
        Args:
            working_dir: Directory to search in
            
        Returns:
            Dict mapping artifact type to list of file paths
        """
        working_path = Path(working_dir)
        artifacts = {
            'junit_xml': [],
            'json_results': [],
            'coverage': [],
            'logs': []
        }
        
        # Common artifact patterns
        patterns = {
            'junit_xml': [
                '**/junit*.xml',
                '**/TEST-*.xml', 
                '**/test-results/**/*.xml',
                '**/target/surefire-reports/*.xml',
                '**/build/test-results/**/*.xml',
                '**/Testing/*/Test.xml'
            ],
            'json_results': [
                '**/test-results*.json',
                '**/jest-results*.json',
                '**/mocha-results*.json',
                '**/.nyc_output/*.json'
            ],
            'coverage': [
                '**/coverage.xml',
                '**/lcov.info',
                '**/coverage/*.json'
            ],
            'logs': [
                '**/test.log',
                '**/tests.log',
                '**/*test*.log'
            ]
        }
        
        for artifact_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                try:
                    matches = list(working_path.glob(pattern))
                    artifacts[artifact_type].extend(matches)
                except:
                    continue  # Skip if pattern fails
        
        return artifacts