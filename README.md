## Developer Twin (LangGraph)

Automated agent developer that:

- Finds GitHub issues labeled `dev-twin`
- Clones the repository, analyzes project type, and optionally generates a `Dockerfile` (with `ripgrep`)
- Plans and implements changes in a loop using tools (shell, file read/write, search, notes)
- Opens a Pull Request when done

### Requirements
- Python 3.10+
- Git on PATH
- Optional: Docker (for containerized runs)
- Optional: ripgrep (`rg`) for faster search/listing


## Walthrough
### Requirements
1. Install git (if not already installed)
2. Install python 3.10+ (if not already installed)
3. Install ripgrep (if not already installed)

### Fill out .env
1. Copy `env.example` to `.env`
2. Fill out the values in `.env` depending on the model you want to use
- [Check Model setup examples](#model-setup-examples) at the end of the README for more information
- [Check Model and performance recommendations](#model-and-performance-recommendations) to see which model is best for you
3. If you want to run the agent on your own GitHub repository, you need to provide a Github token and the repository URL, follow the next steps:

### Github Setup
1. Follow the [Github Token Setup instructions](#github-token) to get your Github token
2. Add your token and the repository URL to the `.env` file

### Setup
1. Run `python -m venv .venv`
2. Run `. .venv/Scripts/Activate.ps1` (Windows) or `source .venv/bin/activate` (Linux/Mac)
3. Run `pip install -r requirements.txt`

### Running the agent
#### Run on your own repository
- Run `python -m src.runner main`
- To run against a specific issue, use `python -m src.runner main --issue N`
  
#### Running demos
- Recommended to just use gemini-2.0-flash for demos, it is fast and inexpensive or even free
- Run `python -m src.runner demo run --bench` to run against all demos
- To run against a specific demo, use `python -m src.runner demo run --name <demo_name>` (demos are located in `demos/`)

#### Running benchmark
- Run `python -m src.runner bench run`
- To only do a limited number of runs, use `python -m src.runner bench run --limit <limit>`
- To skip a specific number of issues, use `python -m src.runner bench run --skip-n <skip_n>`
- To skip a specific repository, use `python -m src.runner bench run --skip-repo <skip_repo>`
- You can also combine these options to skip a repo/number and limit the number of runs, for example: `python -m src.runner bench run --skip-repo astropy/astropy --limit 10`

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

### Model and performance recommendations
- Best overall (recommended): Claude Sonnet 4 via OpenRouter
  - In `.env`: set `PROVIDER=openrouter`, `DEFAULT_MODEL=anthropic/claude-sonnet-4`, and `OPENROUTER_API_KEY`
- Also strong: OpenAI `o4-mini-high` and Google Gemini 2.5 Pro
  - OpenAI: `PROVIDER=openai`, `DEFAULT_MODEL=o4-mini-high` (mapped internally to `o4-mini` with reasoning effort "high")
  - Google: `PROVIDER=google`, `DEFAULT_MODEL=gemini-2.5-pro`
- Fast for demos: `gemini-2.0-flash` (default) – quick and inexpensive for smoke tests

Additional tips:
- Install ripgrep for faster search/listing; the fallback search is slower
- Start with a small repo; set `REPO_URL` in `.env` and run `python -m src.runner`

### Multi-agent vs unified
- Unified agent (default): a single agent with tools that plans and executes end‑to‑end. It uses `plan_update` to refine and update its plan continuously during the run.
- Multi‑agent graph: orchestrates distinct phases via LangGraph: `analysis → setup → planner → coder → test_lint` and iterates between `coder` and `test_lint` until done.

Choose via CLI:
- Unified (default): `python -m src.runner main`
- Multi‑agent: `python -m src.runner main --multi-agent`
- Demos unified: `python -m src.runner demo run`
- Demos multi‑agent: `python -m src.runner demo run --multi-agent`
- Bench unified: `python -m src.runner bench run`
- Bench multi‑agent: `python -m src.runner bench run --multi-agent`

### Usage

- **Standard run**:
  ```bash
  python -m src.runner main
  ```
  - **--issue N**: target a specific issue number
  - **--workdir PATH**: override workspace root (default: `.devtwin_work`)
  - **--docker**: build and run in a container suggested by analysis
  - **--multi-agent**: run the multi‑agent graph instead of the default unified agent
  - **--config-file PATH** and repeated `--config key=value`: customize runtime settings

- **Behavior when env is incomplete**: falls back to a local dry-run using a sample repo; no GitHub/PR is created.

### Demo mode

Prebuilt cases live under `demos/` (each has `repo/` and `issue.md`). Runs the same analysis → setup → planner → coder pipeline.

```bash
# All demos
python -m src.runner demo run

# Specific demo
python -m src.runner demo run --name react_counter

# Options
python -m src.runner demo run --docker
python -m src.runner demo run --workdir D:\\work
python -m src.runner demo run --multi-agent

# Quick demo bench (fast): set PROVIDER=google, DEFAULT_MODEL=gemini-2.0-flash
python -m src.runner demo run --bench
```

Artifacts are written under `<WORKDIR>/demos/<name>/artifacts/`.

### Configuration knobs

Configs live in `config/default.json` (see `config/README.md`). You can provide a custom file with `--config-file` and/or override values with repeated `--config key=value` flags.

- Agent iteration depth: increase `agents.unified.max_steps` (or `agents.coder.max_steps`, etc.) for harder tasks
- History and tool output limits: tune `limits.max_history_chars` and `limits.keep_last_messages`; per‑agent overrides exist as `agents.<name>.max_history_chars` and `agents.<name>.keep_last_messages`

Example overrides:
```bash
python -m src.runner \
  --config agents.unified.max_steps=300 \
  --config limits.max_history_chars=150000 \
  --config limits.keep_last_messages=120
```

### Benchmark mode (SWE-bench Lite)

Run the graph across a dataset of issues.

```bash
python -m src.runner bench run \
  --subset princeton-nlp/SWE-bench_Lite \
  --split test \
  --limit 5 \
  --docker
```

Key options:
- **--subset**: HF dataset path (default `princeton-nlp/SWE-bench_Lite`)
- **--split**: dataset split (default `test`)
- **--limit**: cap number of issues
- **--skip_completed**: skip issues with existing `summary.json`
- **--skip_n**: skip the first N issues in the split
- **--skip_repo**: substring to exclude certain repos
- **--only_type**: `fail`, `pass`, or `all` (default `fail`)
- **--apply_test_patch**: apply provided failing tests (default `True`)
- **--test_timeout**: seconds per test run (default `120`)
- **--docker**: use analysis-suggested Docker image per issue

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

Interpreting results:
- Even if a run ends as "incomplete", the agent may have implemented changes but could not fully resolve tests, environment, or validation. Review `artifacts/` (plan, transcript, events) and the repo diff to assess implemented work.

### How it works

- Orchestrated via a LangGraph state machine:
  - `analysis` → `setup` → `planner` → `coder` → repeat until `done` or max loops
- `analysis`: infers ecosystem, commands, and suggests a Dockerfile (installs `ripgrep`).
- `setup`: prepares environment and validates test runners (Windows-safe commands).
- `planner`: produces strict JSON plan with minimal steps.
 - `coder`: performs incremental edits using tools (read/write/search/shell/notes) and finalizes with a commit message.
 - In the unified flow, the agent maintains a single loop and updates its plan continuously via `plan_update` as it discovers new information.

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

### Model setup examples

Use `.env` to set provider and model:

```env
# OpenRouter + Claude Sonnet 4 (recommended overall)
PROVIDER=openrouter
DEFAULT_MODEL=anthropic/claude-sonnet-4
OPENROUTER_API_KEY=...

# OpenAI + o4-mini-high (mapped internally to o4-mini with reasoning effort "high")
PROVIDER=openai
DEFAULT_MODEL=o4-mini-high
OPENAI_API_KEY=...

# Google + Gemini 2.5 Pro (strong general model)
PROVIDER=google
DEFAULT_MODEL=gemini-2.5-pro
GOOGLE_API_KEY=...

# Fast demo/smoke runs
PROVIDER=google
DEFAULT_MODEL=gemini-2.0-flash
```

