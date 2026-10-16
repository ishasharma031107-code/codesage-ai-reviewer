import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from codesage import checks, gitdiff, cli  # noqa: E402
import fake_ollama  # noqa: E402


def make_demo():
    d = tempfile.mkdtemp()
    subprocess.run(["sh", os.path.join(ROOT, "demo", "make_demo_repo.sh")], cwd=d, check=True, capture_output=True)
    return os.path.join(d, "demo-repo")


class TestCodeSage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = make_demo()
        cls.srv, cls.url = fake_ollama.start()

    def test_parse_diff_line_numbers(self):
        files = gitdiff.parse_diff(gitdiff.get_diff("staged", cwd=self.repo))
        self.assertEqual(len(files), 1)
        lines = dict(files[0].added)
        self.assertIn('API_KEY = "sk-live', lines[4])
        self.assertIn("SELECT", lines[14])

    def test_static_checks(self):
        files = gitdiff.parse_diff(gitdiff.get_diff("staged", cwd=self.repo))
        titles = {i["title"] for i in checks.run_checks(files)}
        for t in ["Possible hardcoded secret", "SQL built with string formatting",
                  "Shell command with shell=True", "Mutable default argument", "Bare except swallows all errors"]:
            self.assertIn(t, titles)

    def _run(self, *extra):
        old = os.getcwd()
        os.chdir(self.repo)
        try:
            out = os.path.join(tempfile.mkdtemp(), "r.json")
            code = cli.main(["review", "--url", self.url, "--format", "json", "-o", out, *extra])
            with open(out) as f:
                return code, json.load(f)
        finally:
            os.chdir(old)

    def test_full_pipeline_with_model(self):
        code, r = self._run("--fail-on", "high")
        self.assertEqual(code, 1)
        ai = [i for i in r["issues"] if i["source"] == "model"]
        self.assertTrue(any(i["title"] == "Crash on empty input" and i["line"] == 22 for i in ai))
        self.assertTrue(r["commit_message"].startswith("feat"))
        self.assertLess(r["score"], 50)

    def test_unreachable_ollama_is_friendly(self):
        old = os.getcwd()
        os.chdir(self.repo)
        try:
            code = cli.main(["review", "--url", "http://127.0.0.1:1"])
        finally:
            os.chdir(old)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
