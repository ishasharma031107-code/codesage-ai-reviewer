"""A fake Ollama server for tests/CI, so the pipeline can be tested without a GPU."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        user = body["messages"][-1]["content"]
        if body.get("format") == "json":
            m = re.search(r"^(\d+): .*(/ len\(|\[0\]|== None)", user, re.M)
            issues = []
            if m:
                issues.append({"line": int(m.group(1)), "category": "bug", "severity": "high",
                               "title": "Crash on empty input", "detail": "Divides by len() / indexes [0] without checking for empty input.",
                               "fix": "Return early if the list is empty."})
            content = "```json\n" + json.dumps({"summary": "Adds helper functions.", "issues": issues}) + "\n```"
        else:
            content = "feat(app): add user lookup and stats helpers\n\n- add average and first-user helpers\n- add db lookup"
        out = json.dumps({"message": {"role": "assistant", "content": content}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)


def start():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"
