# mini-swe-agent-automate-repo-installation

# Simple Pipeline

## Step 1: Repository Name --> DockerFile + Test Command

(Need Anthropic API Key/OPENAI API Key depending on model used, default Claude-4-Sonnet)

- Example Command: `python simple_repo_to_dockerfile.py expressjs/express`

- Output: `DockerFile` and `test_command.json` under `agent-result/$repo_name`

## Step 2: DockerFile + Test Command --> Test Output

- Example Command: `python verify_dockerfile.py agent-result/expressjs-express/Dockerfile`

- Output: `test_output.txt` under `agent-result/$repo_name`

## Step 3: Test Output --> Parser 

- Example Command: `python log_parser/main.py agent-result/expressjs-express/Dockerfile`

- Output: `parsed_test_status.json` with parser name and parsed test status 

# TODO

`simple_repo_to_dockerfile.py`: Currently I'm using the defaultAgent class from Mini-SWE-Agent and so we can't see agent's action on live. Would be nice to replace it with an InteractiveAgent? Also this file is more driven by `dockerfile_generation.yaml` which has all the workflow guidelines for the agent.
`verify_dockerfile.py`: One small improvement could be to avoid running the test twice (once when building DockerFile, once when getting test output). This would need modification to the YAML too (prompt engineering work mostly).
`log_parser/`: Need to implement more parsers? 

With the above improvements done, we should have everything we need to define the profile of a repo automatically by filling in:
  - repo_name (Provided)
  - commit number (Can be found rather easily)
  - DockerFile (Transform the file to string)
  - Log Parser (Import from log_parser)

And so we need a file that thread the above parts up and fill in the profile.

(Lastly, we need a Github Repo Scraper so that we don't need to manually find repos.)

