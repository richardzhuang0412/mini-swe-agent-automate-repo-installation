"""
Unified test result schema for log parser output.

Based on the schema outlined in log_parser/gpt_tips.md, this provides a consistent
format for test results across all parsers and test frameworks.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Literal
from enum import Enum

# Test status types
TestStatus = Literal["pass", "fail", "skip", "xfail", "xpass", "error"]
OverallStatus = Literal["pass", "fail", "error", "partial"]

class TestFramework(Enum):
    """Enumeration of supported test frameworks"""
    PYTEST = "pytest"
    UNITTEST = "unittest" 
    JEST = "jest"
    MOCHA = "mocha"
    VITEST = "vitest"
    GO_TEST = "go-test"
    CARGO = "cargo"
    JUNIT = "junit"
    MAVEN = "maven"
    GRADLE = "gradle"
    CTEST = "ctest"
    PHPUNIT = "phpunit"
    RSPEC = "rspec"
    MINITEST = "minitest"
    BAZEL = "bazel"
    UNKNOWN = "unknown"


@dataclass
class TestCase:
    """Individual test case result"""
    status: TestStatus
    file: Optional[str] = None
    line: Optional[int] = None
    duration_s: Optional[float] = None
    message: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


@dataclass
class OverallResult:
    """Overall test run summary"""
    status: OverallStatus
    exit_code: int
    duration_s: Optional[float] = None
    total_tests: Optional[int] = None
    passed: Optional[int] = None
    failed: Optional[int] = None
    skipped: Optional[int] = None
    errors: Optional[int] = None


@dataclass
class ParserMeta:
    """Metadata about the parsing process"""
    runner: str
    detected_by: list[str] = field(default_factory=list)
    confidence: float = 1.0
    parser_version: str = "1.0"
    structured_format: bool = False
    fallback_used: bool = False


@dataclass
class TestResults:
    """
    Unified test results schema.
    
    This is the standard format returned by all parsers, regardless of the
    underlying test framework or output format.
    """
    schema_version: str = "v1"
    overall: Optional[OverallResult] = None
    tests: Dict[str, TestCase] = field(default_factory=dict)
    meta: Optional[ParserMeta] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON serialization"""
        result = {
            "schema_version": self.schema_version,
            "overall": {
                "status": self.overall.status,
                "exit_code": self.overall.exit_code,
                "duration_s": self.overall.duration_s,
                "total_tests": self.overall.total_tests,
                "passed": self.overall.passed,
                "failed": self.overall.failed,
                "skipped": self.overall.skipped,
                "errors": self.overall.errors,
            } if self.overall else None,
            "tests": {
                test_id: {
                    "status": test.status,
                    "file": test.file,
                    "line": test.line,
                    "duration_s": test.duration_s,
                    "message": test.message,
                    "stdout": test.stdout,
                    "stderr": test.stderr,
                }
                for test_id, test in self.tests.items()
            },
            "meta": {
                "runner": self.meta.runner,
                "detected_by": self.meta.detected_by,
                "confidence": self.meta.confidence,
                "parser_version": self.meta.parser_version,
                "structured_format": self.meta.structured_format,
                "fallback_used": self.meta.fallback_used,
            } if self.meta else None,
        }
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestResults":
        """Create TestResults from dictionary"""
        overall = None
        if data.get("overall"):
            overall_data = data["overall"]
            overall = OverallResult(
                status=overall_data["status"],
                exit_code=overall_data["exit_code"],
                duration_s=overall_data.get("duration_s"),
                total_tests=overall_data.get("total_tests"),
                passed=overall_data.get("passed"),
                failed=overall_data.get("failed"),
                skipped=overall_data.get("skipped"),
                errors=overall_data.get("errors"),
            )
        
        tests = {}
        for test_id, test_data in data.get("tests", {}).items():
            tests[test_id] = TestCase(
                status=test_data["status"],
                file=test_data.get("file"),
                line=test_data.get("line"),
                duration_s=test_data.get("duration_s"),
                message=test_data.get("message"),
                stdout=test_data.get("stdout"),
                stderr=test_data.get("stderr"),
            )
        
        meta = None
        if data.get("meta"):
            meta_data = data["meta"]
            meta = ParserMeta(
                runner=meta_data["runner"],
                detected_by=meta_data.get("detected_by", []),
                confidence=meta_data.get("confidence", 1.0),
                parser_version=meta_data.get("parser_version", "1.0"),
                structured_format=meta_data.get("structured_format", False),
                fallback_used=meta_data.get("fallback_used", False),
            )
        
        return cls(
            schema_version=data.get("schema_version", "v1"),
            overall=overall,
            tests=tests,
            meta=meta,
        )


def create_test_id(file_path: Optional[str], suite: Optional[str], test_name: str) -> str:
    """
    Create a consistent test ID from file path, suite, and test name.
    Format: file_path::suite::test_name or variations based on available info.
    """
    parts = []
    
    if file_path:
        # Use relative path if possible
        parts.append(file_path)
    
    if suite:
        parts.append(suite)
    
    parts.append(test_name)
    
    return "::".join(parts)


def calculate_overall_status(tests: Dict[str, TestCase], exit_code: int) -> OverallStatus:
    """Calculate overall status from individual test results and exit code"""
    if not tests:
        return "error" if exit_code != 0 else "pass"
    
    statuses = [test.status for test in tests.values()]
    
    if "error" in statuses:
        return "error"
    elif "fail" in statuses:
        return "fail"
    elif exit_code != 0:
        return "error"
    elif all(status in ["pass", "skip", "xfail"] for status in statuses):
        return "pass"
    else:
        return "partial"