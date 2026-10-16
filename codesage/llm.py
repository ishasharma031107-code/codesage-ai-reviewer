"""Talk to a local open-weight model through Ollama's HTTP API (stdlib only)."""
import json
import os
import urllib.request
import urllib.error

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("CODESAGE_MODEL", "gemma4")

REVIEW_SYSTEM = """You are CodeSage, a strict senior code reviewer.
You review ONE file's git diff. Only comment on ADDED lines (starting with '+').
Find real problems: bugs, security issues, performance traps, and code-quality issues.
Do not nitpick formatting. Do not invent problems; if the change is fine, return no issues.
Line numbers refer to the NEW file; use the numbers given in the annotated added lines.
Reply with ONLY JSON in this exact shape:
{"summary": "<one sentence on what this change does>",
 "issues": [{"line": <int>, "category": "bug|security|performance|quality",
             "severity": "high|medium|low", "title": "<short>",
             "detail": "<why it is a problem>", "fix": "<concrete fix, code if short>"}]}"""

COMMIT_SYSTEM = """You write git commit messages in Conventional Commits style.
Given a diff summary, reply with ONLY the commit message: a subject line under 72 chars
(type(scope): description), a blank line, then 1-4 short bullet points. No code fences."""


class LLMError(RuntimeError):
    pass


def chat(model, system, user, json_mode=False, url=None, timeout=300):
    body = {"model": model, "stream": False, "options": {"temperature": 0.1},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["format"] = "json"
    req = urllib.request.Request(f"{url or OLLAMA_URL}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["message"]["content"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")
        if "not found" in detail:
            raise LLMError(f"Model '{model}' not pulled. Run: ollama pull {model}") from e
        raise LLMError(f"Ollama error {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise LLMError("Can't reach Ollama. Is it running? Start it with: ollama serve") from e


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            return json.loads(text[s:e + 1])
        raise


def annotate(fd, max_chars=12000):
    """Patch plus an explicit list of added lines with their new-file numbers."""
    lines = "\n".join(f"{n}: {t}" for n, t in fd.added)
    return f"FILE: {fd.path}\n\nDIFF:\n{fd.patch[:max_chars]}\n\nADDED LINES (new line numbers):\n{lines[:max_chars]}"


def review_file(fd, model, url=None):
    raw = chat(model, REVIEW_SYSTEM, annotate(fd), json_mode=True, url=url)
    try:
        data = parse_json(raw)
    except Exception:
        return {"summary": "(model returned unparseable output)", "issues": []}
    valid_lines = {n for n, _ in fd.added}
    issues = []
    for i in data.get("issues") or []:
        if not isinstance(i, dict):
            continue
        try:
            ln = int(i.get("line", 0))
        except (TypeError, ValueError):
            ln = 0
        i["line"] = ln if ln in valid_lines else (min(valid_lines, key=lambda v: abs(v - ln)) if valid_lines and ln else 0)
        i["file"] = fd.path
        i["source"] = "model"
        i.setdefault("severity", "low")
        i.setdefault("category", "quality")
        if i["severity"] not in ("high", "medium", "low"):
            i["severity"] = "low"
        issues.append(i)
    return {"summary": str(data.get("summary", "")), "issues": issues}


def commit_message(file_summaries, stat, model, url=None):
    user = f"Files changed:\n{stat}\n\nPer-file summaries:\n" + "\n".join(
        f"- {p}: {s}" for p, s in file_summaries.items())
    return chat(model, COMMIT_SYSTEM, user, url=url).strip().strip("`").strip()
