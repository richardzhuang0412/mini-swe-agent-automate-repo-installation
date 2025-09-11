#!/usr/bin/env python3
"""
Log Parser CLI - Command line interface for parsing test results.

Usage:
    python -m log_parser.cli dockerfile /path/to/Dockerfile
    python -m log_parser.cli output "test output here" --command "npm test"
    python -m log_parser.cli file /path/to/test-output.txt
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .core.parser import TestLogParser
from .schemas.output import TestResults


class LogParserCLI:
    """Command line interface for the log parser"""
    
    def __init__(self):
        self.parser = TestLogParser()
    
    def main(self):
        """Main CLI entry point"""
        args = self._parse_args()
        
        try:
            if args.command == 'dockerfile':
                result = self._parse_dockerfile(args)
            elif args.command == 'output':
                result = self._parse_output(args)
            elif args.command == 'file':
                result = self._parse_file(args)
            else:
                print(f"Unknown command: {args.command}", file=sys.stderr)
                return 1
            
            # Output results
            if args.format == 'json':
                self._output_json(result, args.output)
            else:
                self._output_summary(result, args.output)
            
            return 0 if result.overall and result.overall.status in ['pass', 'partial'] else 1
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            if args.debug:
                import traceback
                traceback.print_exc()
            return 2
    
    def _parse_args(self):
        """Parse command line arguments"""
        parser = argparse.ArgumentParser(
            description="Parse test output logs into structured format",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
    # Parse from Dockerfile setup
    python -m log_parser.cli dockerfile /path/to/Dockerfile
    
    # Parse raw test output
    python -m log_parser.cli output "test output here" --command "npm test"
    
    # Parse from file
    python -m log_parser.cli file /path/to/test-output.txt
    
    # Output as JSON
    python -m log_parser.cli dockerfile /path/to/Dockerfile --format json
            """
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # Dockerfile command
        dockerfile_parser = subparsers.add_parser('dockerfile', help='Parse from Dockerfile')
        dockerfile_parser.add_argument('dockerfile', type=Path, help='Path to Dockerfile')
        dockerfile_parser.add_argument('--test-commands', type=Path, help='Path to test_commands.json')
        
        # Output command
        output_parser = subparsers.add_parser('output', help='Parse raw test output')
        output_parser.add_argument('output', help='Test output text')
        output_parser.add_argument('--command', help='Test command that was executed')
        output_parser.add_argument('--working-dir', type=Path, help='Working directory for artifact search')
        
        # File command
        file_parser = subparsers.add_parser('file', help='Parse test output from file')
        file_parser.add_argument('file', type=Path, help='Path to test output file')
        file_parser.add_argument('--command', help='Test command that was executed')
        file_parser.add_argument('--working-dir', type=Path, help='Working directory for artifact search')
        
        # Common arguments
        for subparser in [dockerfile_parser, output_parser, file_parser]:
            subparser.add_argument('--format', choices=['summary', 'json'], default='summary',
                                 help='Output format (default: summary)')
            subparser.add_argument('--output', '-o', type=Path, help='Output file (default: stdout)')
            subparser.add_argument('--debug', action='store_true', help='Enable debug output')
        
        args = parser.parse_args()
        
        if not hasattr(args, 'command') or not args.command:
            parser.print_help()
            sys.exit(1)
        
        return args
    
    def _parse_dockerfile(self, args) -> TestResults:
        """Parse test results from Dockerfile"""
        dockerfile_path = args.dockerfile
        
        if not dockerfile_path.exists():
            raise FileNotFoundError(f"Dockerfile not found: {dockerfile_path}")
        
        # Look for test_commands.json in the same directory if not specified
        test_commands_path = args.test_commands
        if not test_commands_path:
            test_commands_path = dockerfile_path.parent / "test_commands.json"
        
        return self.parser.parse_from_dockerfile(dockerfile_path, test_commands_path)
    
    def _parse_output(self, args) -> TestResults:
        """Parse test results from raw output text"""
        return self.parser.parse_from_output(
            args.output,
            args.command,
            args.working_dir
        )
    
    def _parse_file(self, args) -> TestResults:
        """Parse test results from output file"""
        file_path = args.file
        
        if not file_path.exists():
            raise FileNotFoundError(f"Output file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            output = f.read()
        
        return self.parser.parse_from_output(
            output,
            args.command,
            args.working_dir
        )
    
    def _output_json(self, result: TestResults, output_file: Optional[Path]):
        """Output results as JSON"""
        output_data = result.to_dict()
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
        else:
            print(json.dumps(output_data, indent=2, ensure_ascii=False))
    
    def _output_summary(self, result: TestResults, output_file: Optional[Path]):
        """Output results as human-readable summary"""
        lines = []
        
        # Overall status
        if result.overall:
            overall = result.overall
            lines.append("=" * 60)
            lines.append(f"Overall Status: {overall.status.upper()}")
            lines.append(f"Exit Code: {overall.exit_code}")
            
            if overall.duration_s:
                lines.append(f"Duration: {overall.duration_s:.2f}s")
            
            lines.append("")
            
            # Test statistics
            if overall.total_tests:
                lines.append(f"Total Tests: {overall.total_tests}")
                
                if overall.passed:
                    lines.append(f"✓ Passed: {overall.passed}")
                if overall.failed:
                    lines.append(f"✗ Failed: {overall.failed}")
                if overall.skipped:
                    lines.append(f"○ Skipped: {overall.skipped}")
                if overall.errors:
                    lines.append(f"⚠ Errors: {overall.errors}")
                
                lines.append("")
        
        # Test details
        if result.tests:
            lines.append("Test Results:")
            lines.append("-" * 40)
            
            # Group by status
            by_status = {}
            for test_id, test in result.tests.items():
                if test.status not in by_status:
                    by_status[test.status] = []
                by_status[test.status].append((test_id, test))
            
            # Show failures and errors first
            for status in ['fail', 'error', 'xfail', 'xpass', 'pass', 'skip']:
                if status not in by_status:
                    continue
                
                status_symbol = {
                    'pass': '✓',
                    'fail': '✗', 
                    'error': '⚠',
                    'skip': '○',
                    'xfail': '○',
                    'xpass': '⚠'
                }.get(status, '?')
                
                lines.append(f"\n{status.upper()} ({len(by_status[status])}):")
                
                for test_id, test in by_status[status][:10]:  # Limit output
                    duration_str = f" ({test.duration_s:.3f}s)" if test.duration_s else ""
                    lines.append(f"  {status_symbol} {test_id}{duration_str}")
                    
                    if test.message and status in ['fail', 'error']:
                        # Show first line of error message
                        first_line = test.message.split('\n')[0][:80]
                        lines.append(f"     {first_line}")
                
                if len(by_status[status]) > 10:
                    lines.append(f"     ... and {len(by_status[status]) - 10} more")
        
        # Parser metadata
        if result.meta:
            lines.append("")
            lines.append("Parser Info:")
            lines.append(f"  Runner: {result.meta.runner}")
            lines.append(f"  Confidence: {result.meta.confidence:.1%}")
            if result.meta.structured_format:
                lines.append("  Format: Structured")
            else:
                lines.append("  Format: Plain text (fallback)")
            if result.meta.detected_by:
                lines.append(f"  Detected by: {', '.join(result.meta.detected_by[:3])}")
        
        lines.append("=" * 60)
        
        # Write output
        content = '\n'.join(lines)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            print(content)


def main():
    """Entry point for CLI"""
    cli = LogParserCLI()
    sys.exit(cli.main())


if __name__ == '__main__':
    main()