"""Fast deterministic checks that run before the model. Cheap, exact, never hallucinate."""
import re

RULES = [
    ("security", "high", "Possible hardcoded secret",
     re.compile(r"(?i)(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"][^'\"]{6,}['\"]")),
    ("security", "high", "AWS access key",
     re.compile(r"AKIA[0-9A-Z]{16}")),
    ("security", "high", "Private key committed",
     re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("security", "high", "Use of eval/exec on dynamic input",
     re.compile(r"\b(eval|exec)\s*\(")),
    ("security", "medium", "Shell command with shell=True",
     re.compile(r"shell\s*=\s*True")),
    ("security", "high", "SQL built with string formatting",
     re.compile(r"(?i)(execute|query)\s*\(\s*f?['\"].*(SELECT|INSERT|UPDATE|DELETE).*(\{|%s|\"\s*\+|'\s*\+)")),
    ("security", "medium", "Unsafe deserialization (pickle/yaml.load)",
     re.compile(r"pickle\.loads?\(|yaml\.load\((?!.*Loader=yaml\.SafeLoader)")),
    ("security", "medium", "TLS verification disabled",
     re.compile(r"verify\s*=\s*False")),
    ("bug", "medium", "Bare except swallows all errors",
     re.compile(r"^\s*except\s*:\s*(pass)?\s*$")),
    ("bug", "medium", "Mutable default argument",
     re.compile(r"def \w+\(.*=\s*(\[\]|\{\}|set\(\))")),
    ("quality", "low", "Debug print/console.log left in",
     re.compile(r"^\s*(print\(|console\.log\(|debugger;)")),
    ("quality", "low", "TODO/FIXME added",
     re.compile(r"(?i)\b(TODO|FIXME|HACK)\b")),
]


def run_checks(files):
    out = []
    for f in files:
        for ln, text in f.added:
            for cat, sev, msg, rx in RULES:
                if rx.search(text):
                    out.append({"file": f.path, "line": ln, "category": cat, "severity": sev,
                                "title": msg, "detail": text.strip()[:160], "fix": "",
                                "source": "static"})
    return out
