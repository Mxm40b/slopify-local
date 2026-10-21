#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
from pathlib import Path

# parent two times to get out of src/ into project root
PROJECT_DIR = Path(__file__).resolve().parent.parent


def find_executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"{name!r} not found. run this from nix develop.")
    return path


BWRAP = find_executable("bwrap")
# BASH = find_executable("bash")
AGENT_ENV = os.environ["AGENT_ENV"]
CLOSURE = Path(os.environ["AGENT_CLOSURE"]).read_text().split()

store_binds = []
for p in CLOSURE:
    store_binds += ["--ro-bind", p, p]

# if BWRAP is None or BASH is None:
#     raise RuntimeError("Required executables not found. Run this from nix develop.")


def executor(script: str) -> str:

    with open("log", "a") as f:
        f.write(f"Ran:\n```\n{script}\n```\n")
    command = [
        BWRAP,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        # TODO: what does * do? i guess it turns a list within a list into consecutive elements within the surrounding list
        *store_binds,
        "--ro-bind",
        str(PROJECT_DIR / "sandbox/prompt-files"),
        "/prompt",
        "--bind",
        str(PROJECT_DIR / "sandbox/workspace"),
        "/workspace",
        "--bind",
        str(PROJECT_DIR / "sandbox/backup"),
        "/backup",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--chdir",
        "/workspace",
        "--clearenv",
        "--setenv",
        "PATH",
        f"{AGENT_ENV}/bin",
        f"{AGENT_ENV}/bin/bash",
        "--noprofile",
        "--norc",
        "-s",
    ]

    try:
        result = subprocess.run(
            command,
            input=script,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return "[executor] Script exceeded the 10-second timeout."
    return result.stdout[-1500:] + f"\n[exit status: {result.returncode}]"


# TODO: once i have a loop, i will handle this one directly in it, and end the loop. i can remove this function from available_functions too. this structure is for when i need to give the agent more tools.


# TODO: put all tool calls into a log file.


if __name__ == "__main__":
    script = sys.stdin.read()
    raise SystemExit(executor(script))
