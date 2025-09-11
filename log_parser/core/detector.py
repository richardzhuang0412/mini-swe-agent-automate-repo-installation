"""
Test runner detection logic.

Detects test frameworks and runners based on file patterns, manifest files,
executed commands, and output patterns.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ..schemas.output import TestFramework


@dataclass 
class RunnerDetection:
    """Result of test runner detection"""
    runner: TestFramework
    confidence: float  # 0.0 to 1.0
    detected_by: List[str]  # What evidence led to this detection
    language: str
    structured_flags: Dict[str, str]  # Flags that can produce structured output


class TestRunnerDetector:
    """
    Detects test runners and frameworks from various sources of evidence.
    
    Detection sources:
    1. File/manifest patterns (package.json, pyproject.toml, etc.)
    2. Executed command analysis
    3. Output pattern analysis
    """
    
    def __init__(self):
        self.file_patterns = self._init_file_patterns()
        self.command_patterns = self._init_command_patterns()
        self.structured_flags = self._init_structured_flags()
    
    def detect_from_directory(self, directory: Path) -> List[RunnerDetection]:
        """
        Detect test runners based on files in a directory.
        
        Args:
            directory: Path to analyze
            
        Returns:
            List of RunnerDetection results, ordered by confidence
        """
        detections = []
        
        for runner, patterns in self.file_patterns.items():
            confidence = 0.0
            evidence = []
            
            for pattern_info in patterns:
                file_pattern = pattern_info["pattern"]
                weight = pattern_info["weight"]
                
                matches = list(directory.glob(file_pattern))
                if matches:
                    confidence += weight
                    evidence.extend([str(match.name) for match in matches])
            
            if confidence > 0:
                # Additional analysis for some frameworks
                if runner == TestFramework.PYTEST:
                    confidence += self._analyze_python_setup(directory)
                elif runner == TestFramework.JEST:
                    confidence += self._analyze_package_json(directory, "jest")
                elif runner == TestFramework.MOCHA:
                    confidence += self._analyze_package_json(directory, "mocha")
                
                detections.append(RunnerDetection(
                    runner=runner,
                    confidence=min(confidence, 1.0),  # Cap at 1.0
                    detected_by=evidence,
                    language=self._get_language_for_runner(runner),
                    structured_flags=self.structured_flags.get(runner, {})
                ))
        
        # Sort by confidence, highest first
        detections.sort(key=lambda x: x.confidence, reverse=True)
        return detections
    
    def detect_from_command(self, command: str) -> Optional[RunnerDetection]:
        """
        Detect test runner from executed command.
        
        Args:
            command: The command that was executed
            
        Returns:
            RunnerDetection if a runner is identified, None otherwise
        """
        command_lower = command.lower().strip()
        
        for runner, patterns in self.command_patterns.items():
            for pattern in patterns:
                if re.search(pattern, command_lower):
                    return RunnerDetection(
                        runner=runner,
                        confidence=0.8,  # High confidence from command
                        detected_by=[f"command: {command}"],
                        language=self._get_language_for_runner(runner),
                        structured_flags=self.structured_flags.get(runner, {})
                    )
        
        return None
    
    def detect_from_output(self, output: str) -> List[RunnerDetection]:
        """
        Detect test runner from output patterns.
        
        Args:
            output: Test output to analyze
            
        Returns:
            List of possible runners based on output patterns
        """
        detections = []
        output_lower = output.lower()
        
        # Pattern matching for different runners
        patterns = {
            TestFramework.PYTEST: [
                r'=+ test session starts =+',
                r'=+.*pytest.*=+',
                r'\d+ passed.*in \d+\.\d+s',
                r'collected \d+ items?'
            ],
            TestFramework.JEST: [
                r'tests?:\s+\d+ passed',
                r'test suites?:\s+\d+ passed',
                r'jest.*\d+\.\d+\.\d+',
                r'pass.*\d+\.\d+ms'
            ],
            TestFramework.MOCHA: [
                r'\d+ passing \(\d+ms\)',
                r'✓.*\(\d+ms\)',
                r'mocha.*\d+\.\d+\.\d+'
            ],
            TestFramework.GO_TEST: [
                r'ok\s+\S+\s+\d+\.\d+s',
                r'fail\s+\S+\s+\d+\.\d+s',
                r'--- pass:.*\(\d+\.\d+s\)',
                r'--- fail:.*\(\d+\.\d+s\)'
            ],
            TestFramework.CARGO: [
                r'test result: ok\. \d+ passed',
                r'running \d+ tests?',
                r'test.*ok',
                r'cargo test'
            ]
        }
        
        for runner, runner_patterns in patterns.items():
            matches = 0
            evidence = []
            
            for pattern in runner_patterns:
                if re.search(pattern, output_lower):
                    matches += 1
                    evidence.append(f"output pattern: {pattern}")
            
            if matches > 0:
                # Confidence based on number of pattern matches
                confidence = min(matches / len(runner_patterns), 0.7)  # Max 0.7 for output-only detection
                
                detections.append(RunnerDetection(
                    runner=runner,
                    confidence=confidence,
                    detected_by=evidence,
                    language=self._get_language_for_runner(runner),
                    structured_flags=self.structured_flags.get(runner, {})
                ))
        
        detections.sort(key=lambda x: x.confidence, reverse=True)
        return detections
    
    def combine_detections(self, detections: List[RunnerDetection]) -> List[RunnerDetection]:
        """
        Combine multiple detection results, merging evidence for the same runner.
        """
        runner_map = {}
        
        for detection in detections:
            if detection.runner in runner_map:
                # Merge with existing detection
                existing = runner_map[detection.runner]
                existing.confidence = max(existing.confidence, detection.confidence)
                existing.detected_by.extend(detection.detected_by)
            else:
                runner_map[detection.runner] = detection
        
        combined = list(runner_map.values())
        combined.sort(key=lambda x: x.confidence, reverse=True)
        return combined
    
    def _init_file_patterns(self) -> Dict[TestFramework, List[Dict[str, any]]]:
        """Initialize file patterns for different test frameworks"""
        return {
            TestFramework.PYTEST: [
                {"pattern": "pytest.ini", "weight": 0.9},
                {"pattern": "pyproject.toml", "weight": 0.6},
                {"pattern": "tox.ini", "weight": 0.4},
                {"pattern": "setup.cfg", "weight": 0.3},
                {"pattern": "tests/**/*test*.py", "weight": 0.3},
                {"pattern": "**/test_*.py", "weight": 0.3},
                {"pattern": "requirements*test*.txt", "weight": 0.2}
            ],
            TestFramework.UNITTEST: [
                {"pattern": "**/test_*.py", "weight": 0.4},
                {"pattern": "tests/**/*.py", "weight": 0.2}
            ],
            TestFramework.JEST: [
                {"pattern": "jest.config.*", "weight": 0.9},
                {"pattern": "package.json", "weight": 0.6},  # Need to check content
                {"pattern": "**/*.test.{js,ts,jsx,tsx}", "weight": 0.4},
                {"pattern": "**/*.spec.{js,ts,jsx,tsx}", "weight": 0.4},
                {"pattern": "__tests__/**/*.{js,ts,jsx,tsx}", "weight": 0.3}
            ],
            TestFramework.MOCHA: [
                {"pattern": ".mocharc.*", "weight": 0.9},
                {"pattern": "mocha.opts", "weight": 0.8},
                {"pattern": "package.json", "weight": 0.5},  # Need to check content
                {"pattern": "test/**/*.{js,ts}", "weight": 0.3}
            ],
            TestFramework.VITEST: [
                {"pattern": "vitest.config.*", "weight": 0.9},
                {"pattern": "vite.config.*", "weight": 0.4},
                {"pattern": "**/*.test.{js,ts,jsx,tsx}", "weight": 0.3}
            ],
            TestFramework.GO_TEST: [
                {"pattern": "go.mod", "weight": 0.8},
                {"pattern": "**/*_test.go", "weight": 0.9}
            ],
            TestFramework.CARGO: [
                {"pattern": "Cargo.toml", "weight": 0.8},
                {"pattern": "tests/**/*.rs", "weight": 0.4},
                {"pattern": "src/**/*test*.rs", "weight": 0.2}
            ],
            TestFramework.MAVEN: [
                {"pattern": "pom.xml", "weight": 0.9},
                {"pattern": "src/test/java/**/*.java", "weight": 0.4}
            ],
            TestFramework.GRADLE: [
                {"pattern": "build.gradle*", "weight": 0.9},
                {"pattern": "src/test/**/*.{java,kt}", "weight": 0.4}
            ],
            TestFramework.PHPUNIT: [
                {"pattern": "phpunit.xml*", "weight": 0.9},
                {"pattern": "composer.json", "weight": 0.5},
                {"pattern": "tests/**/*Test.php", "weight": 0.4}
            ],
            TestFramework.RSPEC: [
                {"pattern": ".rspec", "weight": 0.9},
                {"pattern": "Gemfile", "weight": 0.5},
                {"pattern": "spec/**/*_spec.rb", "weight": 0.6}
            ]
        }
    
    def _init_command_patterns(self) -> Dict[TestFramework, List[str]]:
        """Initialize command patterns for different test frameworks"""
        return {
            TestFramework.PYTEST: [r'pytest', r'python\s+-m\s+pytest'],
            TestFramework.UNITTEST: [r'python\s+-m\s+unittest'],
            TestFramework.JEST: [r'jest', r'npm\s+test.*jest', r'yarn\s+test.*jest'],
            TestFramework.MOCHA: [r'mocha', r'npm\s+test.*mocha', r'yarn\s+test.*mocha'],
            TestFramework.VITEST: [r'vitest'],
            TestFramework.GO_TEST: [r'go\s+test'],
            TestFramework.CARGO: [r'cargo\s+test'],
            TestFramework.MAVEN: [r'mvn\s+test', r'maven.*test'],
            TestFramework.GRADLE: [r'gradle\s+test', r'gradlew\s+test'],
            TestFramework.PHPUNIT: [r'phpunit'],
            TestFramework.RSPEC: [r'rspec'],
            TestFramework.CTEST: [r'ctest']
        }
    
    def _init_structured_flags(self) -> Dict[TestFramework, Dict[str, str]]:
        """Initialize structured output flags for different frameworks"""
        return {
            TestFramework.PYTEST: {
                "junit_xml": "--junitxml=results/junit.xml",
                "json": "--json-report --json-report-file=results/pytest.json"
            },
            TestFramework.JEST: {
                "json": "--json --outputFile=results/jest.json --testLocationInResults"
            },
            TestFramework.MOCHA: {
                "json": "--reporter json --reporter-options output=results/mocha.json",
                "junit_xml": "--reporter xunit --reporter-options output=results/mocha.xml"
            },
            TestFramework.VITEST: {
                "junit_xml": "--reporter=junit --outputFile=results/vitest.xml"
            },
            TestFramework.GO_TEST: {
                "json": "-json"
            },
            TestFramework.CARGO: {
                "json": "-- --format=json -Z unstable-options"
            }
        }
    
    def _get_language_for_runner(self, runner: TestFramework) -> str:
        """Get the primary language for a test runner"""
        language_map = {
            TestFramework.PYTEST: "python",
            TestFramework.UNITTEST: "python",
            TestFramework.JEST: "javascript",
            TestFramework.MOCHA: "javascript", 
            TestFramework.VITEST: "javascript",
            TestFramework.GO_TEST: "go",
            TestFramework.CARGO: "rust",
            TestFramework.MAVEN: "java",
            TestFramework.GRADLE: "java",
            TestFramework.JUNIT: "java",
            TestFramework.CTEST: "c++",
            TestFramework.PHPUNIT: "php",
            TestFramework.RSPEC: "ruby",
            TestFramework.MINITEST: "ruby",
            TestFramework.BAZEL: "mixed",
            TestFramework.UNKNOWN: "unknown"
        }
        return language_map.get(runner, "unknown")
    
    def _analyze_python_setup(self, directory: Path) -> float:
        """Additional analysis for Python projects"""
        boost = 0.0
        
        # Check pyproject.toml for pytest configuration
        pyproject_path = directory / "pyproject.toml"
        if pyproject_path.exists():
            try:
                import tomllib
                content = pyproject_path.read_text()
                if "pytest" in content or "[tool.pytest" in content:
                    boost += 0.3
            except:
                pass
        
        # Check for pytest in requirements files
        for req_file in ["requirements.txt", "requirements-test.txt", "test-requirements.txt"]:
            req_path = directory / req_file
            if req_path.exists():
                content = req_path.read_text().lower()
                if "pytest" in content:
                    boost += 0.2
        
        return boost
    
    def _analyze_package_json(self, directory: Path, framework: str) -> float:
        """Additional analysis for Node.js projects"""
        package_json_path = directory / "package.json"
        if not package_json_path.exists():
            return 0.0
        
        try:
            with open(package_json_path) as f:
                package_data = json.load(f)
            
            boost = 0.0
            
            # Check dependencies
            for dep_type in ["dependencies", "devDependencies"]:
                deps = package_data.get(dep_type, {})
                if framework in deps:
                    boost += 0.4
            
            # Check scripts
            scripts = package_data.get("scripts", {})
            test_script = scripts.get("test", "").lower()
            if framework in test_script:
                boost += 0.3
            
            return boost
        except:
            return 0.0