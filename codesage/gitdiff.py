"""Get a git diff and split it into per-file chunks."""
import subprocess
from dataclasses import dataclass, field


class GitError(RuntimeError):
    pass


def git(*args, cwd=None) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise GitError(p.stderr.strip() or f"git {' '.join(args)} failed")
    return p.stdout


@dataclass
class FileDiff:
    path: str
    patch: str
    added: list = field(default_factory=list)  # (line_no, text) of added lines

    @property
    def n_added(self):
        return len(self.added)


def get_diff(mode="staged", rev=None, cwd=None) -> str:
    if mode == "staged":
        return git("diff", "--cached", "--unified=3", cwd=cwd)
    if mode == "working":
        return git("diff", "--unified=3", cwd=cwd)
    if mode == "range":
        return git("diff", "--unified=3", rev, cwd=cwd)
    if mode == "last":
        return git("show", "--format=", "--unified=3", "HEAD", cwd=cwd)
    raise ValueError(mode)


def parse_diff(text: str) -> list:
    files, cur, new_line = [], None, 0
    for line in text.splitlines():
        if line.startswith("diff --git "):
            if cur:
                files.append(cur)
            cur = FileDiff(path=line.split(" b/", 1)[-1], patch="")
        if cur is None:
            continue
        cur.patch += line + "\n"
        if line.startswith("+++ "):
            if line.strip() == "+++ /dev/null":
                cur.path += " (deleted)"
        elif line.startswith("@@"):
            # @@ -a,b +c,d @@
            plus = line.split("+", 1)[1].split(" ", 1)[0]
            new_line = int(plus.split(",")[0])
        elif line.startswith("+"):
            cur.added.append((new_line, line[1:]))
            new_line += 1
        elif line.startswith("-"):
            pass
        elif not line.startswith("\\"):
            new_line += 1
    if cur:
        files.append(cur)
    return [f for f in files if "Binary files" not in f.patch]
