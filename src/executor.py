#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
from pathlib import Path

from config import config

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
KVM_LIST = [
    "--dev-bind",
    "/dev/kvm",
    "/dev/kvm",
]
RENDERD128_LIST = [
    "--dev-bind",
    "/dev/dri/renderD128",
    "/dev/dri/renderD128",
]
MUVM_LIST = [
    *RENDERD128_LIST,
    *KVM_LIST,
    # "--dir",
    # "/run/user/1000",
    "--dir",
    "/run",
    "--dir",
    "/var/tmp",
    "--dir",
    "/sys",
    "--dir",
    "/dev/shm",
    "--dir",
    "/var/run",
    "--ro-bind",
    str(PROJECT_DIR / "sandbox/etc/resolv.conf"),
    "/etc/resolv.conf",
    "--setenv",
    "XDG_RUNTIME_DIR",
    "/tmp/xdg",
    # "--perms",
    # "0700",
    # "--tmpfs",
    # "/run/user/1000",
]


def executor(script: str) -> str:

    with open("log", "a") as f:
        f.write(f"Ran:\n```\n{script}\n```\n")
    command = [
        BWRAP,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
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
        "--perms",
        "0700",
        "--dir",
        "/tmp/xdg",
        "--chdir",
        "/workspace",
        "--clearenv",
        "--setenv",
        "PATH",
        f"{AGENT_ENV}/bin",
        "--setenv",
        "HOME",
        "/workspace",
        "--ro-bind",
        str(PROJECT_DIR / "sandbox/etc/passwd"),
        "/etc/passwd",
        "--ro-bind",
        str(PROJECT_DIR / "sandbox/etc/group"),
        "/etc/group",
        *MUVM_LIST,
        f"{AGENT_ENV}/bin/bash",
        "--noprofile",
        "--norc",
        "-s",
    ]
    # TODO: for kvm, renderD128, /dev/fuse, /dev/net/tun, add config options to make it opt in.

    try:
        result = subprocess.run(
            command,
            input=script,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=config["tools_config"]["script_timeout"],
            check=False,
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return f"[executor] Script exceeded the {config['tools_config']['script_timeout']}-second timeout."
    if len(result.stdout) > 1600:
        return (
            result.stdout[:800]
            + f"\n---\n{len(result.stdout) - 1600} characters cut\n---\n"
            + result.stdout[-800:]
            + f"\n[exit status: {result.returncode}]"
        )
    else:
        return result.stdout + f"\n[exit status: {result.returncode}]"


if __name__ == "__main__":
    script = sys.stdin.read()
    raise SystemExit(executor(script))
