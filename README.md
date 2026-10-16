# 🧙 CodeSage: AI code review for your git diff, 100% local

CodeSage reviews your staged changes **before you commit** using an **open-weight model running locally via Ollama** (Gemma 4 by default). It flags bugs, security holes and code-quality problems with line numbers and concrete fixes, then writes a Conventional Commits message for you.

No cloud API, no keys, your code never leaves your machine. Zero Python dependencies.

## How it works
```
git diff ─► parse into per-file hunks (exact new-file line numbers)
        ├─► static rules: secrets, SQL injection, shell=True, eval, bare except, ...  (fast, exact)
        └─► Gemma 4 via Ollama, one call per file, JSON-mode review  (bugs the rules can't see)
                 │
                 ▼
    validate model output (clamp line numbers to real added lines, fix bad fields)
    merge + dedupe ─► score /100 ─► terminal / markdown / JSON report
                 │
                 └─► second model call: commit message ─► optional `--commit`
```
Static checks catch the obvious things deterministically; the model catches logic bugs (e.g. division by zero on empty input). Every finding is tagged `[static]` or `[ai]`.

## Quick start
```bash
# 1. Ollama + a model
ollama pull gemma4            # or any model: qwen2.5-coder, llama3.1, ...
# 2. Install
pip install .                 # or run without installing: python -m codesage review
# 3. Try the demo (creates a repo with a buggy staged change)
sh demo/make_demo_repo.sh && cd demo-repo
codesage review
```

## Usage
```bash
codesage review                      # staged changes (default)
codesage review --working            # unstaged changes
codesage review --last               # last commit
codesage review --range main..feat   # a branch / PR
codesage review --commit             # review, then commit with the generated message
codesage review --format markdown -o review.md   # paste into a PR
codesage review --fail-on high       # exit 1 on high-severity issues (CI)
codesage review --static-only        # rules only, no model
codesage review --model qwen2.5-coder
codesage install-hook                # pre-commit hook that blocks high-severity issues
```
Env vars: `CODESAGE_MODEL`, `OLLAMA_URL`.

## Tests
```bash
python -m unittest discover tests -v
```
Tests run the full pipeline against a fake Ollama server, so no GPU needed.

## License
MIT
