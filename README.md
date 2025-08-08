## Developer Twin (LangGraph)

Automated multi-agent developer that:

- Finds GitHub issues labeled `dev-twin`
- Clones the repository, analyzes project type, and optionally generates a `Dockerfile` (with `ripgrep`)
- Plans and implements changes in a loop using tools (shell, file read/write, search, notes)
- Opens a Pull Request when done

### Requirements

- Python 3.10+
- Git on PATH
- Optional: Docker (for containerized runs)
- Optional: ripgrep (`rg`) for faster search/listing

### Environment

Create a `.env` from `env.example`:

```
GITHUB_TOKEN=
REPO_URL=

# LLM Provider Configuration
# Choose one provider: google, openai, anthropic, openrouter
PROVIDER=google

# LLM API Keys
GOOGLE_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OPENROUTER_API_KEY=

# Model Configuration
DEFAULT_MODEL=gemini-2.0-flash

# Optional custom base URL for OpenAI-compatible APIs
BASE_URL=

# Working directory for clones/artifacts
WORKDIR=.devtwin_work
```

Notes:
- `REPO_URL` is used to resolve `owner/repo` for GitHub API calls.
- Supported PROVIDER values: `google`, `openai`, `anthropic`, `openrouter`.
- You must provide the matching API key for the selected provider.

### Github Token
Visit https://github.com/settings/personal-access-tokens and generate a new token
 - give it a name
 - give it access to either all repositories or select specific repositories
 - add the following repository permissions:
    - contents
    - issues
    - pull requests
    - discussions

### Install

```bash
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

### Recommendations
- For AI Models, use a smart model that is good at tool use and coding like claude sonnet 4, gemini 2.5 pro, and potentially gpt-5 etc, performance highly depends on the model
- Install ripgrep for faster search/listing, default search is slow
- Try out the standard run with a small repo first by providing the REPO_URL in the env file and running `python -m src.main`

### Usage

- **Standard run**:
  ```bash
  python -m src.main
  ```
  - **--issue N**: target a specific issue number
  - **--workdir PATH**: override workspace root (default: `.devtwin_work`)
  - **--docker**: build and run in a container suggested by analysis

- **Behavior when env is incomplete**: falls back to a local dry-run using a sample repo; no GitHub/PR is created.

### Demo mode

Prebuilt cases live under `demos/` (each has `repo/` and `issue.md`). Runs the same analysis → setup → planner → coder pipeline.

```bash
# All demos
python -m src.main demo run

# Specific demo
python -m src.main demo run --name react_counter

# Options
python -m src.main demo run --docker
python -m src.main demo run --workdir D:\\work
```

Artifacts are written under `<WORKDIR>/demos/<name>/artifacts/`.

### Benchmark mode (SWE-bench Lite)

Run the graph across a dataset of issues.

```bash
python -m src.main bench run \
  --subset princeton-nlp/SWE-bench_Lite \
  --split test \
  --limit 5 \
  --docker
```

Key options:
- **--subset**: HF dataset path (default `princeton-nlp/SWE-bench_Lite`)
- **--split**: dataset split (default `test`)
- **--limit**: cap number of examples
- **--skip_completed**: skip examples with existing `summary.json`
- **--skip_repo**: substring to exclude certain repos
- **--only_type**: `fail`, `pass`, or `all` (default `fail`)
- **--apply_test_patch**: apply provided failing tests (default `True`)
- **--test_timeout**: seconds per test run (default `120`)
- **--docker**: use analysis-suggested Docker image per example

### Outputs (artifacts)

For each run, artifacts are saved under `<WORKDIR>/<owner__repo>/issue-<n>/artifacts/` (or demo/bench equivalents):
- `analysis.json`: project type, build/test/run commands, package manager, optional Dockerfile
- `plan.json`: minimal actionable plan
- `transcript.json`: LLM interaction trace
- `events.json`: tool call events
- `notes.md`: human-readable notes distilled from `.devtwin_notes.jsonl`
- `status.jsonl`: live status updates
- `summary.json` and `summary.md`: short end-of-run summary
- `Dockerfile`: if analysis suggested one

### How it works

- Orchestrated via a LangGraph state machine:
  - `analysis` → `setup` → `planner` → `coder` → repeat until `done` or max loops
- `analysis`: infers ecosystem, commands, and suggests a Dockerfile (installs `ripgrep`).
- `setup`: prepares environment and validates test runners (Windows-safe commands).
- `planner`: produces strict JSON plan with minimal steps.
- `coder`: performs incremental edits using tools (read/write/search/shell/notes) and finalizes with a commit message.

### Generated Dockerfile

When applicable, a simple Dockerfile is proposed based on detected stack (Node/Python, etc.) and includes `ripgrep`.

### Safety & Notes

- Executes shell non-interactively; uses timeouts and adds non-interactive flags where possible.
- Creates a feature branch and opens a PR via GitHub API using `GITHUB_TOKEN` (requires `repo` scope).
- Tool usage and model outputs are constrained via strict JSON schemas.

### Troubleshooting

- Ensure `git` is on PATH and `GITHUB_TOKEN` has `repo` scope.
- Choose a valid `PROVIDER` and provide the corresponding API key.
- On Windows, prefer `python -m pytest` and `where` (the system does this automatically where relevant).
- Install `ripgrep` for best performance; the fallback search is slower.

