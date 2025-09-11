# Log Parser

A comprehensive test log parser that converts test output from any language/framework into a unified JSON schema.

## Overview

This log parser implements the battle-tested workflow described in `gpt_tips.md`:

1. **Execute tests** with proper output capture and environment setup
2. **Detect test runner** from files, commands, and output patterns  
3. **Try structured parsing** first (JUnit XML, Jest JSON, Go JSON, etc.)
4. **Fall back to line patterns** for plain text outputs
5. **Return consistent schema** regardless of input format

## Features

- **Multi-language support**: Python (pytest, unittest), JavaScript (Jest, Mocha), Go, Rust, Java, and more
- **Structured format parsers**: JUnit XML, Jest JSON, Go test JSON
- **Line-pattern fallbacks**: Regex-based parsing for plain text outputs  
- **Unified schema**: Consistent output format across all parsers
- **Test runner detection**: Automatic framework detection from multiple sources
- **CLI interface**: Easy command-line usage

## Installation

The log parser is part of the mini-swe-agent project. Simply run it from the project directory:

```bash
# Set Python path
export PYTHONPATH=/path/to/mini_swe_agent

# Use the parser
python -m log_parser --help
```

## Usage

### 1. Parse from Dockerfile Setup

The main use case - parse tests by running them from a Dockerfile:

```bash
python -m log_parser dockerfile /path/to/Dockerfile
```

This will:
- Load test commands from `test_commands.json` 
- Set up a test environment from the Dockerfile
- Run tests with proper output capture
- Parse results using structured formats or fallbacks

### 2. Parse Raw Test Output

Parse test output directly:

```bash
python -m log_parser output "your test output here" --command "npm test"
```

### 3. Parse from File

Parse test output from a file:

```bash
python -m log_parser file /path/to/test-output.txt --command "pytest"
```

### Output Formats

- `--format summary` (default): Human-readable summary
- `--format json`: Structured JSON output

### Example JSON Output

```json
{
  "schema_version": "v1",
  "overall": {
    "status": "fail",
    "exit_code": 1,
    "duration_s": 0.03,
    "total_tests": 3,
    "passed": 2,
    "failed": 1,
    "skipped": 0,
    "errors": 0
  },
  "tests": {
    "test_math.py::test_addition": {
      "status": "pass",
      "file": "test_math.py",
      "duration_s": null,
      "message": null
    },
    "test_math.py::test_subtraction": {
      "status": "fail", 
      "file": "test_math.py",
      "message": "assert 2 == 3"
    }
  },
  "meta": {
    "runner": "pytest",
    "detected_by": ["header: =+ test session starts =+"],
    "confidence": 1.0,
    "structured_format": false,
    "fallback_used": true
  }
}
```

## Architecture

### Core Components

- **`core/parser.py`**: Main orchestrator that coordinates all parsing strategies
- **`core/harness.py`**: Test execution with output capture and ANSI stripping  
- **`core/detector.py`**: Test runner detection from files, commands, and output
- **`schemas/output.py`**: Unified test result schema and data classes

### Adapters

- **`adapters/junit_xml.py`**: JUnit XML parser (pytest, Maven, Gradle, PHPUnit, etc.)
- **`adapters/jest_json.py`**: Jest JSON output parser
- **`adapters/go_json.py`**: Go test JSON parser (`go test -json`)
- **`adapters/line_patterns.py`**: Regex-based fallback parsers for plain text

### Supported Frameworks

| Language | Frameworks | Structured Format | Line Patterns |
|----------|------------|------------------|---------------|
| Python | pytest, unittest | JUnit XML | ✅ pytest, unittest |
| JavaScript | Jest, Mocha, Vitest | Jest JSON, JUnit XML | ✅ Jest, Mocha |
| Go | go test | JSON (`-json`) | ✅ go test |
| Rust | cargo test | - | ✅ cargo |
| Java | JUnit, Maven, Gradle | JUnit XML | ✅ JUnit |
| PHP | PHPUnit | JUnit XML | ⚠️ Basic |
| Ruby | RSpec, minitest | - | ⚠️ Basic |
| C/C++ | CTest, gtest | CTest XML | - |

✅ = Full support, ⚠️ = Basic support, - = Not implemented

## Integration with simple_repo_to_dockerfile.py

The enhanced `simple_repo_to_dockerfile.py` now generates both:

1. **Dockerfile**: Container setup with test execution
2. **test_commands.json**: Test command metadata

Example `test_commands.json`:
```json
{
  "test_command": "npm test",
  "test_framework": "jest",
  "language": "javascript", 
  "env_vars": {
    "NODE_ENV": "test"
  },
  "structured_output_flags": {
    "json_flag": "--json --outputFile=results/jest.json",
    "junit_flag": "--reporters=default --reporters=jest-junit"
  }
}
```

## Extending the Parser

### Adding New Structured Format Parsers

1. Create a new parser in `adapters/`
2. Implement `parse_file()` and `parse_string()` methods
3. Return `TestResults` objects
4. Register in `core/parser.py`

### Adding New Line Pattern Parsers

1. Create a new `PatternSignature` subclass in `adapters/line_patterns.py`
2. Implement `score()` and `parse_test_cases()` methods
3. Add to the signatures dictionary

### Adding New Test Runner Detection

1. Add patterns to `core/detector.py`
2. Update file patterns, command patterns, and structured flags
3. Test detection accuracy

## Testing

Run the test suite:

```bash
python test_log_parser.py
```

This tests:
- Pytest output parsing
- Go test output parsing  
- JUnit XML parsing
- Integration with existing examples

## Design Philosophy

The parser follows these principles from `gpt_tips.md`:

1. **Structured formats first**: Always prefer machine-readable output
2. **Deterministic fallbacks**: Regex patterns with confidence scoring
3. **Unified schema**: Consistent output regardless of input format
4. **Defensive parsing**: Handle malformed input gracefully
5. **Extensible architecture**: Easy to add new frameworks

This ensures reliable parsing across "anything a repo can throw at you" while maintaining consistency and performance.