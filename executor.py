#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
from pathlib import Path

from ollama import ChatResponse, chat

PROJECT_DIR = Path(__file__).resolve().parent


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


def run_script(script: str) -> str:
    """This is a tool for interacting with the filesystem and executing various commands, with available commands in $PATH."""
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
        )
    except subprocess.TimeoutExpired:
        return "[executor] Script exceeded the 10-second timeout."
    return result.stdout[-4000:] + f"\n[exit status: {result.returncode}]"


def end_loop(end_message: str, successful: bool):
    """This is the tool that you call to end the loop, once you're confident either the task is finished or that it can't be finished with the available tools, by you.
    Provide your final answers through end_message, even if they are failures (in which case you should say why). Assume that anything you say prior to this tool call is not read by the user.
    end_message is the text that you want to write for the user once you have finished the task to inform them of what you did, or what you couldn't do, without too much detail. the successful flag is for you to tell the user whether you succeeded or failed (or think you won't succeed)."""


# TODO: once i have a loop, i will handle this one directly in it, and end the loop. i can remove this function from available_functions too. this structure is for when i need to give the agent more tools.

available_functions = {f.__name__: f for f in (run_script, end_loop)}
tools = list(available_functions.values())

# this program is for agents, so 64k context or more is recommended.
MAX_TOKENS_SIZE = 2**16
# fixed for now, will eventually become variable depending on task.
MAX_STEPS = 20
MAX_MISSES = 3


# TODO: figure out the optimal way to write this:
SLOPIFY_LOCAL_CONTEXT = f"You are an agent that has to do what the user asks. You can use the shell (you are in an isolated environment), and can read from everywhere, execute programs in the $PATH, do all your work in /workspace including your final result. /workspace is writeable and persistent. /prompt is read-only and may contain files that the user has provided, that you can copy and work on in /workspace; if the user talks about files they have provided, they will be in /prompt; you can look inside with the run_script tool. Nothing that you say will be accessible to the user; instead, provide your answers through the end_loop tool. If you do not have commands that are necessary to finish the task, you can ask for them with the end_loop tool. You have at most {MAX_STEPS} steps."


def loop(prompt):
    messages = [
        {"role": "system", "content": SLOPIFY_LOCAL_CONTEXT},
        # {"role": "user", "content": prompt},
    ]
    listing = run_script("ls -la /prompt")
    messages.append(
        {"role": "user", "content": f"{prompt}\n\nFiles in /prompt:\n{listing}"}
    )
    consecutive_tool_call_misses = 0
    for step in range(MAX_STEPS):
        # TODO: allow for different, non-hardcoded models.
        response: ChatResponse = chat(
            # TODO: change end to make this work
            # model="gemma4:e2b",
            # model="qwen3:4b",
            model="ornith-1.5:9b",
            messages=messages,
            tools=tools,
            think=False,
            options={"num_ctx": MAX_TOKENS_SIZE},
        )
        # if response.prompt_eval_count and response.prompt_eval_duration:
        #     print(response.prompt_eval_count / (response.prompt_eval_duration / 1e9))
        n = response.prompt_eval_count
        t = response.prompt_eval_duration
        if n and t:
            print(f"prefill: {n / (t / 1e9):.1f} tok/s ({n} tokens)")
        if (
            bool(response.prompt_eval_count)
            and response.prompt_eval_count > MAX_TOKENS_SIZE * 3 / 4
        ):
            # TODO: when we're close to the limit, the llm will be prompted to explain what it did; then a new messages will be created, with only the prompt and that explainer. maybe this could be done through a HANDOFF_TOOL.
            return ("Aborting when we're almost at the token limit.", 1)

        messages.append(response.message)
        # print("Thinking: ", response.message.thinking)
        # print("Content: ", response.message.content)
        if response.message.tool_calls:
            for tc in response.message.tool_calls:
                if tc.function.name == "end_loop":
                    args = tc.function.arguments
                    return (
                        args.get("end_message", "No end message provided by the llm"),
                        0 if args.get("successful", False) else 1,
                    )
                if consecutive_tool_call_misses > MAX_MISSES:
                    return (
                        f"The agent tried to use unavailable tools, or did not use any tools, {MAX_MISSES} times in a row.",
                        # random error number lmao
                        3,
                    )
                if tc.function.name in available_functions:
                    consecutive_tool_call_misses = 0
                    # TODO: understand what ** does
                    try:
                        result = available_functions[tc.function.name](
                            **tc.function.arguments
                        )
                    except TypeError:
                        messages.append(
                            {
                                "role": "tool",
                                "content": f"arguments {tc.function.arguments} not understood",
                            }
                        )
                        continue
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": tc.function.name,
                            "content": str(result),
                        }
                    )
                else:
                    consecutive_tool_call_misses += 1
                    messages.append(
                        {
                            "role": "tool",
                            "content": f"The tool you attempted to use, {tc.function.name} is not provided. Available tools are: {(available_functions.keys())}",
                        }
                    )
        else:
            consecutive_tool_call_misses += 1
            messages.append(
                {
                    "role": "user",
                    "content": f"You did not use any tools in this round. If you finished, you can use the end_loop tool. Available tools are: {(available_functions.keys())}",
                }
            )
        if consecutive_tool_call_misses > MAX_MISSES:
            return (
                f"The agent tried to use unavailable tools, or did not use any tools, {MAX_MISSES} times in a row.",
                # random error number lmao
                3,
            )
    return (f"Step limit of {MAX_STEPS} reached.", 2)


# TODO: put all tool calls into a log file.


# if __name__ == "__main__":
#     script = sys.stdin.read()
#     raise SystemExit(run_script(script))

if __name__ == "__main__":
    prompt = sys.stdin.read()
    result: tuple = loop(prompt)
    print(result[0])
    if result[1] > 0:
        raise SystemExit(result[1])
