"""Terminal + markdown + JSON output."""
import json
import os
import sys

_COLOR = sys.stdout.isatty() and os.getenv("NO_COLOR") is None
SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
SEV_ICON = {"high": "🔴", "medium": "🟠", "low": "🟡"}


def c(code, s):
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


SEV_COLOR = {"high": "1;31", "medium": "1;33", "low": "33"}


def dedupe(issues):
    """One finding per file+line. Keep the highest severity; prefer the AI's text (it has a fix),
    and tag it [static+ai] when both sources agree."""
    best = {}
    for i in issues:
        k = (i["file"], i["line"])
        cur = best.get(k)
        if cur is None:
            best[k] = dict(i)
            continue
        sev = min(cur["severity"], i["severity"], key=lambda s: SEV_ORDER.get(s, 3))
        keep = dict(i) if i["source"] == "model" and cur["source"] == "static" else cur
        if {cur["source"], i["source"]} == {"static", "model"}:
            keep["source"] = "static+ai"
            static = cur if cur["source"] == "static" else i
            keep["category"] = static["category"]
        keep["severity"] = sev
        best[k] = keep
    return sorted(best.values(), key=lambda x: (SEV_ORDER.get(x["severity"], 3), x["file"], x["line"]))


def score(issues):
    pen = {"high": 25, "medium": 10, "low": 3}
    return max(0, 100 - sum(pen.get(i["severity"], 0) for i in issues))


def terminal(result):
    issues, summaries = result["issues"], result["summaries"]
    print(c("1;36", "\n━━━ CodeSage review ━━━") + c("2", f"  model: {result['model']}  files: {len(summaries)}"))
    for path, s in summaries.items():
        print(c("1", f"  • {path}") + c("2", f" — {s}"))
    if not issues:
        print(c("1;32", "\n✅ No issues found.\n"))
    for i in issues:
        sev = i["severity"]
        tag = c(SEV_COLOR[sev], f"{SEV_ICON[sev]} {sev.upper():6}")
        src = c("2", {"static": "[static]", "model": "[ai]"}.get(i["source"], "[static+ai]"))
        loc = f"{i['file']}:{i['line']}"
        print(f"\n{tag} {c('1', i['title'])}  {c('36', loc)} {c('2', i['category'])} {src}")
        if i.get("detail"):
            print(f"   {i['detail']}")
        if i.get("fix"):
            print(c("32", "   fix: ") + str(i["fix"]).replace("\n", "\n        "))
    counts = {s: sum(1 for i in issues if i["severity"] == s) for s in ("high", "medium", "low")}
    sc = result["score"]
    col = "1;32" if sc >= 80 else "1;33" if sc >= 50 else "1;31"
    print(c("1", "\n━━━ Summary ━━━"))
    print(f"   {counts['high']} high · {counts['medium']} medium · {counts['low']} low   score: " + c(col, f"{sc}/100"))
    if result.get("commit_message"):
        print(c("1", "\n━━━ Suggested commit message ━━━"))
        print(c("32", result["commit_message"]))
    print()


def markdown(result):
    lines = [f"# CodeSage review", "", f"Model: `{result['model']}` · Score: **{result['score']}/100**", "",
             "## Files", *[f"- `{p}`: {s}" for p, s in result["summaries"].items()], "", "## Issues"]
    if not result["issues"]:
        lines.append("No issues found. ✅")
    for i in result["issues"]:
        lines += [f"### {SEV_ICON[i['severity']]} {i['title']} (`{i['file']}:{i['line']}`)",
                  f"*{i['severity']} · {i['category']} · {i['source']}*", "", i.get("detail", "")]
        if i.get("fix"):
            lines += ["", f"**Fix:** {i['fix']}"]
        lines.append("")
    if result.get("commit_message"):
        lines += ["## Suggested commit message", "```", result["commit_message"], "```"]
    return "\n".join(lines)


def as_json(result):
    return json.dumps(result, indent=2)
