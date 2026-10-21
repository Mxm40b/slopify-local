#!/usr/bin/env python3


import sys

from ollama import ChatResponse, chat

from config import config
from tools import *

# TODO: set defaults if variables not set in slopify.toml
MAX_TOKENS_SIZE = config["model_config"]["max_tokens_size"]
MAX_STEPS = config["model_config"]["max_steps"]
MAX_MISSES = config["model_config"]["max_misses"]

# # this program is for agents, so 64k context or more is recommended.
# MAX_TOKENS_SIZE = 2**16
# # fixed for now, will eventually become variable depending on task.
# MAX_STEPS = 5
# MAX_MISSES = 3


# TODO: figure out the optimal way to write this:
# TODO: fix this to be correct
# SLOPIFY_LOCAL_CONTEXT = f"You are an agent that has to do what the user asks. You can use the shell (you are in an isolated environment), and can read from everywhere, execute programs in the $PATH, do all your work in /workspace including your final result. /workspace is writeable and persistent. /prompt is read-only and may contain files that the user has provided, that you can copy and work on in /workspace; if the user talks about files they have provided, they will be in /prompt; you can look inside with the run_script tool. Nothing that you say will be accessible to the user; instead, provide your answers through the end_loop tool. If you do not have commands that are necessary to finish the task, you can ask for them with the request tool. Every once in a while, use the describe tool to explain what you did in the last five steps. You have at most {MAX_STEPS} steps."
SLOPIFY_LOCAL_CONTEXT = config["model_prompts"]["world_context"]


def loop(prompt):
    with open("log", "a") as f:
        f.write(f'\n\n\n\n===Prompt===\n"{prompt}"\n\n')

    previous_for_step_passes = 0
    while True:
        summary_exists = True
        try:
            summary = open("summary.txt", "r").read()
        except FileNotFoundError:
            summary_exists = False

        messages = [
            {"role": "system", "content": SLOPIFY_LOCAL_CONTEXT},
            # {"role": "user", "content": prompt},
        ]
        prompt_listing = run_script("ls -la /prompt")
        workspace_listing = run_script("ls -la /workspace")
        messages.extend(
            (
                {
                    "role": "user",
                    "content": f"{prompt}\n\nFiles in /prompt:\n{prompt_listing}",
                },
                {
                    "role": "user",
                    "content": f"{prompt}\n\nFiles in /workspace:\n{workspace_listing}",
                },
                {
                    "role": "user",
                    "content": f"context: {config['user']['prompt_context']}",
                },
                {
                    "role": "user",
                    "content": "Never, NEVER, ask the user how tools work. You should experiment with them and figure it out on your own.",
                },
            )
        )
        if summary_exists:
            messages.append(
                {
                    "role": "user",
                    "content": f"Handoff report from your previous session (already done, don't redo it):\n{summary}",
                }
            )
        consecutive_tool_call_misses = 0
        restart_loop = False
        tools = usual_tools
        available_functions = usual_available_functions

        prev_n = 0
        for step in range(MAX_STEPS):
            # TODO: think of a cleaner implementation for this:
            # if step % 5 == 4:
            #     print("asking to describe")
            #     messages.append(
            #         {
            #             "role": "user",
            #             "content": "Please use the describe tool to explain what you did in the last five steps.",
            #         }
            #     )
            response: ChatResponse = chat(
                model=config["general"]["main_model"],
                messages=messages,
                tools=tools,
                think=config["general"]["think"],
                options={"num_ctx": MAX_TOKENS_SIZE},
            )
            # print(response)
            # if response.prompt_eval_count and response.prompt_eval_duration:
            #     print(response.prompt_eval_count / (response.prompt_eval_duration / 1e9))
            print(f"\nStep #{step + previous_for_step_passes}")

            n = response.prompt_eval_count
            t = response.prompt_eval_duration
            if n and t:
                print(f"prefill: {(n - prev_n) / (t / 1e9):.1f} tok/s ({n} tokens)")
            if n:
                prev_n = n
            messages.append(response.message)
            with open("log", "a") as f:
                f.write(f"\n\nStep #{step + previous_for_step_passes}\n")
                if config["logs"]["log_thoughts"]:
                    th = response.message.thinking
                    if th:
                        f.write("\nThinking: \n" + th + "\n\n")
                if config["logs"]["log_output"]:
                    con = response.message.content
                    if con:
                        f.write("\nContent: \n" + con + "\n\n")

            if response.message.tool_calls:
                for tc in response.message.tool_calls:
                    if tc.function.name == "end_loop":
                        args = tc.function.arguments
                        return (
                            args.get(
                                "end_message", "No end message provided by the llm"
                            ),
                            0 if args.get("successful", False) else 1,
                        )
                    elif tc.function.name == "request":
                        try:
                            available_functions["request"](**tc.function.arguments)
                        except TypeError:
                            messages.append(
                                {
                                    "role": "tool",
                                    "content": f"arguments {tc.function.arguments} not understood",
                                }
                            )
                            continue
                        # request tool call succeeded here

                        return (
                            "You can change the env as the agent asked, or refuse, then re-run with the same prompt. \nIf, instead, you want to start a new chat, delete `summary.txt`.",
                            1,
                        )
                    elif tc.function.name == "summarize":
                        try:
                            available_functions[tc.function.name](
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
                        # the call succeeded
                        restart_loop = True
                        previous_for_step_passes += config["model_config"]["max_steps"]
                        break

                    elif tc.function.name in available_functions:
                        consecutive_tool_call_misses = 0
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
                        print(tc.function.name)
                        messages.append(
                            {
                                "role": "tool",
                                "content": f"The tool you attempted to use, {tc.function.name} is not provided. Available tools are: {(available_functions.keys())}",
                            }
                        )
                    if consecutive_tool_call_misses > MAX_MISSES:
                        return (
                            f"The agent tried to use unavailable tools, or did not use any tools, {MAX_MISSES} times in a row.",
                            # random error number lmao
                            3,
                        )
            else:
                consecutive_tool_call_misses += 1
                messages.append(
                    {
                        "role": "user",
                        "content": f"You did not use any tools in this round. If you finished, you can use the end_loop tool. Available tools are: {(available_functions.keys())}",
                    }
                )

            if (
                bool(response.prompt_eval_count)
                and response.prompt_eval_count > MAX_TOKENS_SIZE * 3 / 4
            ) or (
                step >= MAX_STEPS - MAX_MISSES
            ):  # leave steps in case the agent doesn't use the summarize tool correctly
                print("asking to summarize")
                tools = end_tools
                available_functions = end_available_functions
                messages.append(
                    {
                        "role": "user",
                        "content": "Attention!!! Please drop immediately your task, and use the summarize tool to write a handoff report about everything you have done so far. Alternatively, if you have finished your task, you can use end_loop. If you do not use the summarize tool, all progress will be lost (your chat history will be wiped). You can make that summary detailed enough for the next agent to continue. Doesn't matter if you're not entirely sure, just say what you have done so far.",
                    }
                )
            if restart_loop:
                break

            if consecutive_tool_call_misses > MAX_MISSES:
                return (
                    f"The agent tried to use unavailable tools, or did not use any tools, {MAX_MISSES} times in a row.",
                    # random error number lmao
                    3,
                )
        # TODO: remove summary.txt at the end of the loop
        # return (f"Step limit of {MAX_STEPS} reached.", 2)


if __name__ == "__main__":
    # TODO: support setting prompt through slopify.toml
    if not config["user"]["use_toml_prompt"]:
        if sys.stdin.isatty():
            print("Write your prompt:")
            prompt = input()
        else:
            prompt = sys.stdin.read()
    else:
        print("Using prompt provided in slopify.toml")
        prompt = config["user"]["prompt"]
    result: tuple = loop(prompt)
    print(result[0])
    if result[1] > 0:
        raise SystemExit(result[1])
