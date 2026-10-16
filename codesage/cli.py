"""CodeSage CLI: review a git diff with a local open-weight model."""
import argparse
import os
import stat
import sys
from concurrent.futures import ThreadPoolExecutor

from . import __version__, checks, gitdiff, llm, report

HOOK = """#!/bin/sh
# CodeSage pre-commit hook: blocks commits with high-severity issues.
codesage review --staged --fail-on high --no-commit-msg || {
  echo "CodeSage found high-severity issues. Fix them or commit with --no-verify."; exit 1; }
"""


def run_review(args, cwd=None):
    mode = "range" if args.range else "last" if args.last else "working" if args.working else "staged"
    text = gitdiff.get_diff(mode, args.range, cwd=cwd)
    files = gitdiff.parse_diff(text)
    files = [f for f in files if f.n_added and not any(f.path.endswith(x) for x in args.ignore)]
    if not files:
        hint = " (did you `git add`?)" if mode == "staged" else ""
        print(f"Nothing to review{hint}.")
        return None

    static = checks.run_checks(files)
    summaries, model_issues = {}, []
    if args.static_only:
        summaries = {f.path: f"{f.n_added} added lines" for f in files}
    else:
        print(f"🔎 Reviewing {len(files)} file(s) with {args.model} ...", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            results = list(ex.map(lambda f: llm.review_file(f, args.model, args.url), files))
        for f, r in zip(files, results):
            summaries[f.path] = r["summary"]
            model_issues += r["issues"]

    issues = report.dedupe(static + model_issues)
    result = {"model": "static-only" if args.static_only else args.model,
              "summaries": summaries, "issues": issues, "score": report.score(issues)}

    if not args.no_commit_msg and not args.static_only:
        stat_txt = "\n".join(f"{f.path} (+{f.n_added})" for f in files)
        result["commit_message"] = llm.commit_message(summaries, stat_txt, args.model, args.url)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(prog="codesage", description="AI code review on your git diff, 100% local.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("review", help="review a diff")
    g = r.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true", help="staged changes (default)")
    g.add_argument("--working", action="store_true", help="unstaged working-tree changes")
    g.add_argument("--last", action="store_true", help="the last commit")
    g.add_argument("--range", metavar="A..B", help="a commit range, e.g. main..feature")
    r.add_argument("--model", default=llm.DEFAULT_MODEL, help="Ollama model (default: %(default)s)")
    r.add_argument("--url", default=None, help="Ollama URL (default: $OLLAMA_URL or localhost:11434)")
    r.add_argument("--format", choices=["terminal", "markdown", "json"], default="terminal")
    r.add_argument("-o", "--output", help="write report to file")
    r.add_argument("--fail-on", choices=["high", "medium", "low"], help="exit 1 if an issue this severe exists")
    r.add_argument("--static-only", action="store_true", help="skip the model, run only rule checks")
    r.add_argument("--no-commit-msg", action="store_true", help="don't generate a commit message")
    r.add_argument("--commit", action="store_true", help="commit staged changes with the generated message")
    r.add_argument("--jobs", type=int, default=2, help="files reviewed in parallel")
    r.add_argument("--ignore", nargs="*", default=[".lock", ".min.js", ".svg", "package-lock.json"])

    sub.add_parser("install-hook", help="install a git pre-commit hook")
    args = p.parse_args(argv)

    try:
        if args.cmd == "install-hook":
            root = gitdiff.git("rev-parse", "--show-toplevel").strip()
            path = os.path.join(root, ".git", "hooks", "pre-commit")
            with open(path, "w") as f:
                f.write(HOOK)
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
            print(f"Installed pre-commit hook at {path}")
            return 0

        result = run_review(args)
        if result is None:
            return 0
        if args.format == "terminal" and not args.output:
            report.terminal(result)
        else:
            out = report.markdown(result) if args.format in ("markdown", "terminal") else report.as_json(result)
            if args.output:
                with open(args.output, "w") as f:
                    f.write(out)
                print(f"Report written to {args.output}")
            else:
                print(out)

        if args.commit:
            msg = result.get("commit_message")
            if not msg:
                print("No commit message generated; not committing.", file=sys.stderr)
                return 1
            gitdiff.git("commit", "-m", msg)
            print("✅ Committed.")

        if args.fail_on:
            limit = report.SEV_ORDER[args.fail_on]
            if any(report.SEV_ORDER[i["severity"]] <= limit for i in result["issues"]):
                return 1
        return 0
    except (gitdiff.GitError, llm.LLMError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
