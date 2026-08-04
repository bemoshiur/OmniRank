"""Apply a generated unified diff with the real `git apply`, not a simulation.

A diff that LOOKS right in a string comparison and corrupts the file on disk is
exactly the failure mode this release's blockers shipped with -- so every test
that claims a diff "applies" must prove it against the actual tool that will
run it in CI and in a contributor's checkout, byte for byte, not against a
hand-rolled patcher that might share the generator's own blind spots.

Bytes in, bytes out: `subprocess.run` is called WITHOUT `text=True` on purpose.
Python's text-mode pipes perform universal-newline translation on both stdin
and stdout, which would corrupt a CRLF or lone-CR diff before git ever saw it --
silently defeating the one thing the CRLF tests exist to check.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def git_apply_check(root: Path, diff: str) -> subprocess.CompletedProcess:
    """`git apply --check <diff>` against `root`. Does not touch any file."""
    return subprocess.run(
        ["git", "apply", "--check", "-"],
        input=diff.encode("utf-8"), cwd=root, capture_output=True)


def git_apply(root: Path, diff: str) -> subprocess.CompletedProcess:
    """`git apply <diff>` against `root`. Mutates the file(s) the diff touches."""
    return subprocess.run(
        ["git", "apply", "-"],
        input=diff.encode("utf-8"), cwd=root, capture_output=True)


def apply_and_read(root: Path, relative: str, diff: str) -> bytes:
    """Apply `diff` (asserting success) and return the touched file's raw bytes."""
    result = git_apply(root, diff)
    assert result.returncode == 0, (
        f"git apply failed:\nstdout={result.stdout!r}\nstderr={result.stderr!r}\n"
        f"diff=\n{diff}")
    return (root / relative).read_bytes()
