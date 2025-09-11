I want a automatic pipeline that turns any given repo into an execution environment through dockerfile. To do that, I need basically 2 things: 
1. given a repo, figure out how to install it and run its test suite
2. write a log parser that parses test output into a dictionary of test - status pairs

I have an agent that performs step 1 for me but I'm struggling to do step 2. This is because if step 1 is done properly, normally we should expect all tests to be passed and so the parser wouldn't be able to see failed/other non-successful cases. Also, I cannot rely on standard test format entirely (like pytest) because it could be any repo of any language.

I am thinking about leaving step 2 to an agent too but I want you to brainstorm with me what is the exact workflow/if there is any mechanistic way of determining test output format and how to parse that

Love this problem. Here’s a battle-tested way to make Step 2 work across “anything a repo can throw at you,” without assuming pytest or any single ecosystem.

Plan at a glance
	1.	Capture everything reliably → tee stdout/stderr, exit codes, timings, strip ANSI.
	2.	Detect the test runner (fast heuristics over files + command lines actually executed).
	3.	Prefer machine-readable reruns (flip flags/envs to force JSON/XML where possible).
	4.	Parse via adapters (runner-specific parsers first).
	5.	Fallbacks if unknown/unstructured: per-file (or per-test) isolation + line-classifier/regex.
	6.	Always return a uniform schema ({test_id: {status, duration, file, message}}).

Below is how you can make this fully automatic and deterministic, while keeping room for an agent to fill gaps.

⸻

0) Make your harness “parser-friendly”

Have your Step-1 agent (or your wrapper) run tests via a small harness that:
	•	Records:
	•	start/end timestamps, exit code, working dir, env
	•	full stdout + stderr in separate files + combined log
	•	Normalizes: strip ANSI/color codes; optionally also save a raw copy
	•	Sets env to encourage machine-readable output:
	•	CI=true, FORCE_COLOR=0, NO_COLOR=1, PYTEST_ADDOPTS="-q", MOCHA_REPORTER=spec, etc.
	•	Imposes soft limits: per-test command timeout, memory limit, line limit (to avoid 100MB logs)
	•	Runs inside the Docker container so behavior is reproducible

This gives your parser deterministic, clean inputs.

⸻

1) Detect the test runner (fast heuristics)

Run these cheaply before or right after your Step-1 test run:

File/manifest cues (presence → likely runner):
	•	Python: pyproject.toml, pytest.ini, tox.ini, requirements*.txt, setup.cfg, tests/
	•	JS/TS: package.json (scripts.test, deps like jest/mocha/vitest), jest.config.*, vitest.config.*
	•	Java (JUnit): Maven pom.xml, Gradle build.gradle*
	•	Go: go.mod, *_test.go
	•	Rust: Cargo.toml, tests/, #[test]
	•	C/C++: CTestTestfile.cmake, CMakeLists.txt, Makefile with test, gtest includes
	•	PHP: phpunit.xml*, composer deps
	•	Ruby: Gemfile, spec/ (rspec), test/ (minitest)
	•	Bazel/Buck: WORKSPACE, BUILD, BUCK
	•	Haskell: *.cabal, stack.yaml, hspec deps
	•	R: DESCRIPTION, tests/testthat
	•	Others: sbt, dune, elixir mix, etc.

Command cue (what the agent actually executed): capture it. Even if it was npm test, you can resolve it to the underlying runner via package.json scripts.

Store a runner_guess with confidence and hints (which files/commands led you there).

⸻

2) Two-pass strategy: try to force a structured format

Once you have a probable runner, re-run (cheaply) with flags that emit JSON/XML without changing test logic:
	•	pytest: pytest -q --maxfail=0 --durations=0 --junitxml=results/junit.xml (or --json-report)
	•	unittest: python -m pytest often exists; if not, xmlrunner or nose2 --plugin nose2.plugins.junitxml
	•	nose: --with-xunit --xunit-file results/nose.xml
	•	jest: --json --outputFile=results/jest.json --testLocationInResults
	•	mocha: --reporter json > results/mocha.json (or mocha-junit-reporter)
	•	vitest: --reporter=junit --outputFile results/vitest.xml
	•	go test: -json ./... > results/go.json
	•	cargo test: -- --format=json -Z unstable-options (stable alt: -- -Z unstable-options varies; otherwise parse)
	•	maven surefire: results in target/surefire-reports/*.xml; gradle: build/test-results/test/*.xml
	•	ctest: ctest --output-on-failure -T Test (XML in Testing/*/Test.xml)
	•	phpunit: --log-junit results/phpunit.xml
	•	rspec: --format documentation or --format j --out results/rspec.json (needs plugin)

If this succeeds and artifacts exist, parse those and you’re done for most repos.

⸻

3) Adapters: runner-specific parsers

Implement small parsers per format, all mapping into one uniform schema:

{
  "schema_version": "v1",
  "overall": { "status": "pass|fail|error|partial", "exit_code": 1, "duration_s": 12.34 },
  "tests": {
    "path::suite::case": {
      "status": "pass|fail|skip|xfail|xpass|error",
      "file": "tests/test_math.py",
      "line": 42,
      "duration_s": 0.012,
      "message": "AssertionError: expected 2, got 3",
      "stdout": "...",  // optional, trimmed
      "stderr": "..."   // optional
    }
  },
  "meta": { "runner": "pytest", "detected_by": ["pyproject.toml","pytest.ini"] }
}

Adapters to prioritize:
	•	JUnit XML (covers JUnit, Gradle, Maven, phpunit, pytest’s --junitxml, many others)
	•	Jest JSON
	•	Go -json
	•	CTest XML
	•	Mocha/Vitest JSON
	•	Rust cargo (parse stdout JSON objects per line)

⸻

4) Fallbacks when no structured output is available

4a) Line-pattern “generic” parser (zero-assumption)
	•	Strip ANSI → split lines
	•	Scan with a library of regex signatures, each with a score:
	•	Go: ^ok\s+(\S+)\s+([0-9.]+)s$, ^FAIL\s+(\S+)\s+([0-9.]+)s$, --- FAIL: (\S+) \(([\d.]+)s\)
	•	pytest (plain): ^([^ ]+::[^ ]+)\s+(PASSED|FAILED|SKIPPED|ERROR)$, summary =+ (\d+) passed, (\d+) failed...
	•	jest/mocha: ✓|✕ (.*?) \(([0-9.]+)ms\); summary Tests:\s+(\d+) failed, (\d+) passed
	•	junit-ish: [INFO] Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)
	•	ctest: \d+/%\d+\s+Test\s+#\d+:\s+(.*?)\s+\.+\s+(Passed|Failed)
	•	rspec: (\d+)\s+examples?,\s+(\d+)\s+failures?
	•	phpunit: Tests:\s+(\d+), Assertions:\s+(\d+), Failures:\s+(\d+), Errors:\s+(\d+), Skipped:\s+(\d+)
	•	bazel: //path:target\s+(PASSED|FAILED)
	•	Pick the best-matching signature (highest score by counts + coverage) and parse out case lines + summary.
	•	If only a summary is found (no per-case lines), return aggregate only, mark test granularity as suite_only.

4b) Per-file isolation probe (semi-structured)

When the global log is opaque, run a fast second pass that tries to isolate failures/pass per test file:
	•	Discover candidate test files by glob patterns per language:
	•	Python: tests/**/test_*.py, **/*_test.py
	•	JS/TS: **/*.test.{js,ts,tsx}, **/*.spec.*
	•	Go: **/*_test.go
	•	Rust: tests/**/*.rs
	•	C/C++: CTest manifests or test/*
	•	For each file, try the file-scoped invocation:
	•	pytest: pytest -q path/to/test_file.py
	•	jest/vitest/mocha: pass filename
	•	go: go test ./... -run <file_base_without_ext> (not perfect, but works often); or go test ./pkg
	•	cargo: cargo test --test <file_stem> when in tests/
	•	maven/gradle: filters are class-oriented; map file→class where possible
	•	Parse each isolated run with the line-pattern parser; aggregate results.
This gets you per-file pass/fail even if per-case is hard.

4c) Per-test reruns (framework-aware)

If you know the runner, you can go deeper:
	•	pytest: pytest -q -k 'name', or list tests via pytest --collect-only -q
	•	jest: jest -t 'regex' --json --outputFile ...
	•	go: go test -run '^TestName$' -v -json
	•	cargo: cargo test TestName -- --exact --format=json (flags vary)
Use this to turn suite-only logs into per-case results when needed.

⸻

5) What if everything “passed,” so you never see failure shapes?

Good news: you don’t need failures to build a reliable parser when you prefer structured formats, because the schema includes status already. To ensure your unstructured fallback handles failures too, you can:
	•	Synthetic failure injection (optional, only in sandbox):
	•	For Python/JS/Go, pick one discovered test case and re-run only that case with a faulty env flag (e.g., INJECT_FAIL=1) and add a tiny runtime shim that asserts on the flag for that test file. (This requires writing a disposable temp helper alongside the test file; keep it language-scoped and only in ephemeral containers.)
	•	Or use mutation testing light: wrap assert or common test helpers via preload/shim where ecosystems allow (LD_PRELOAD for C/C++; PYTHONPATH shims; Node’s --require hook).
	•	Historic corpus: keep a small corpus of real logs (pass+fail) per runner and run your signature suite against it in CI to validate your regexes.

If synthetic is too intrusive, rely on the machine-readable pass + regex coverage unit tests from a curated log corpus.

⸻

6) Orchestration algorithm (deterministic)

Pseudocode for the whole Step 2:

run = execute_tests_with_harness()

artifacts = {
  raw_stdout, raw_stderr, combined_log,
  exit_code, start_ts, end_ts
}

detection = detect_runner(repo_tree, run.command, combined_log)

# Try structured re-run if feasible and cheap
if detection.runner in STRUCTURED_FLAGS and not artifactsContainStructured(run):
    structured_run = execute_tests_with_harness(extra_flags=STRUCTURED_FLAGS[detection.runner])
    structured_artifacts = collect_structured_artifacts(structured_run)
else:
    structured_artifacts = find_existing_structured_artifacts(repo_tree)

if structured_artifacts:
    result = parse_structured(structured_artifacts, detection)
else:
    result = parse_unstructured(combined_log)
    if result.granularity == "suite_only":
        # Try per-file isolation to refine
        per_file = isolate_by_file_and_parse(detection, repo_tree)
        result = merge(result, per_file)

return normalize_to_schema(result, meta={runner_guess, confidence, exit_code, durations})


⸻

7) Practical tips that make this robust
	•	Strip ANSI first: many runners use emojis/UTF-8/boxes. Also normalize Unicode widths.
	•	Time boxing: when doing per-file probing, cap to N files or T seconds to avoid explosion.
	•	Dedup: Some runners print case lines multiple times (retries); keep the latest status per test id.
	•	ID stability: Build test ids as relative_file::suite_path::test_name. Fall back to a hash of the line if names are missing.
	•	Skips/xfail: track as explicit statuses; not “pass”.
	•	Exit code precedence: if exit≠0 and you parsed zero failures, mark overall status="error" with message="nonzero exit" so callers see a red state.
	•	Artifacts: look for target/surefire-reports, build/test-results, Test.xml, junit*.xml, coverage/**.
	•	Docker defaults: set TZ=UTC, LANG=C.UTF-8, deterministic locales to keep parser stable.

⸻

8) Minimal code skeletons (snippets)

ANSI stripper (Python):

import re
ANSI = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
def strip_ansi(s: str) -> str:
    return ANSI.sub('', s)

Signature picker:

SIGNATURES = [go_sig, pytest_sig, jest_sig, junit_sig, phpunit_sig, ctest_sig, bazel_sig, rspec_sig]

def best_signature(log: str):
    scores = [(sig.name, sig.score(log)) for sig in SIGNATURES]
    scores.sort(key=lambda x: x[1], reverse=True)
    name, score = scores[0]
    return next(sig for sig in SIGNATURES if sig.name == name), score

Example pytest-ish line parser:

PYTEST_CASE = re.compile(r'^(?P<case>[^ ]+::[^ ]+)\s+(?P<status>PASSED|FAILED|SKIPPED|ERROR)\s*$')
PYTEST_SUMMARY = re.compile(r'=+.*?(\d+)\s+passed.*?(?:(\d+)\s+failed)?', re.IGNORECASE)

def parse_pytest_plain(log_lines):
    tests = {}
    for ln in log_lines:
        m = PYTEST_CASE.match(ln)
        if m:
            cid = m.group('case')
            status = m.group('status').lower()
            tests[cid] = {"status": status}
    # summary fallback
    return tests

JUnit XML to unified schema:

from xml.etree import ElementTree as ET

def parse_junit(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    out = {}
    for ts in root.iter('testsuite'):
        for tc in ts.iter('testcase'):
            cid = f"{tc.get('file') or ts.get('name')}::{tc.get('classname')}::{tc.get('name')}"
            status = 'pass'
            msg = None
            dur = float(tc.get('time') or 0)
            for child in list(tc):
                tag = child.tag.lower()
                if tag in ('failure','error'):
                    status = 'fail' if tag=='failure' else 'error'
                    msg = (child.get('message') or '')[:500]
                elif tag == 'skipped':
                    status = 'skip'
            out[cid] = {"status": status, "duration_s": dur, "message": msg}
    return out


⸻

9) Where an agent helps (but you still stay deterministic)

Let an agent augment two parts without being on the critical path:
	•	If the fallback parser can’t classify the log with enough confidence, the agent can propose the rerun flags to force JSON/XML for the detected runner.
	•	If the repo uses a niche framework, the agent can draft a new signature (regex + unit test) and add it to your signature library.

Everything else stays mechanistic and repeatable.

⸻

10) Deliverables checklist for Step 2
	•	Harness that captures logs, exit codes, timing, strips ANSI, sets CI env
	•	Runner detector (files + executed command + log sniff) → {runner, confidence}
	•	Structured rerun map (runner → flags, artifact paths)
	•	Parsers: JUnit, Jest JSON, Go JSON, CTest XML, Mocha/Vitest JSON, Cargo/pytest plain
	•	Generic line-pattern fallback + signature scoring
	•	Per-file isolation probe (framework-aware commands)
	•	Unified JSON schema + merger + exit-code reconciliation
	•	Corpus & unit tests (logs for pass+fail across runners)

If you want, I can turn this into a small Python package layout with stub adapters and a CLI (repo2results) so you can drop it into your Dockerized pipeline.