#!/bin/sh
# Creates ./demo-repo with a clean commit and a buggy staged change to review live.
set -e
rm -rf demo-repo && mkdir demo-repo && cd demo-repo
git init -q
git config user.name "demo"; git config user.email "demo@example.com"
cat > app.py <<'EOF'
import sqlite3


def get_db():
    return sqlite3.connect("users.db")
EOF
git add app.py && git commit -qm "initial"

cat > app.py <<'EOF'
import sqlite3
import subprocess

API_KEY = "sk-live-9f8a7b6c5d4e3f2a1b"


def get_db():
    return sqlite3.connect("users.db")


def find_user(name):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE name = '{name}'")
    return cur.fetchone()


def average_age(users):
    total = 0
    for u in users:
        total += u["age"]
    return total / len(users)


def add_tag(tag, tags=[]):
    tags.append(tag)
    return tags


def backup(path):
    subprocess.run("tar czf backup.tgz " + path, shell=True)


def load_config(path):
    try:
        return open(path).read()
    except:
        pass
EOF
git add app.py
echo "Demo repo ready: cd demo-repo && codesage review"
