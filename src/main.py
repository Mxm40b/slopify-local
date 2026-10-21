#!/usr/bin/env python3


import sys

from ollama import ChatResponse, chat

from config import config
from tools import *

# this program is for agents, so 64k context or more is recommended.
MAX_TOKENS_SIZE = 2**16
# fixed for now, will eventually become variable depending on task.
MAX_STEPS = 50
MAX_MISSES = 3


# TODO: figure out the optimal way to write this:
SLOPIFY_LOCAL_CONTEXT = f"You are an agent that has to do what the user asks. You can use the shell (you are in an isolated environment), and can read from everywhere, execute programs in the $PATH, do all your work in /workspace including your final result. /workspace is writeable and persistent. /prompt is read-only and may contain files that the user has provided, that you can copy and work on in /workspace; if the user talks about files they have provided, they will be in /prompt; you can look inside with the run_script tool. Nothing that you say will be accessible to the user; instead, provide your answers through the end_loop tool. If you do not have commands that are necessary to finish the task, you can ask for them with the end_loop tool. Every once in a while, use the describe tool to explain what you did in the last five steps. You have at most {MAX_STEPS} steps."


def loop(prompt):
    with open("log", "a") as f:
        f.write(f'\n\n\n\n===Prompt===\n"{prompt}"\n\n')

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
        if step % 5 == 4:
            print("asking to describe")
            messages.append(
                {
                    "role": "user",
                    "content": "Please use the describe tool to explain what you did in the last five steps.",
                }
            )
        response: ChatResponse = chat(
            model=config["general"]["main_model"],
            messages=messages,
            tools=tools,
            think=config["general"]["think"],
            options={"num_ctx": MAX_TOKENS_SIZE},
        )
        # if response.prompt_eval_count and response.prompt_eval_duration:
        #     print(response.prompt_eval_count / (response.prompt_eval_duration / 1e9))
        print(f"\nStep #{step}")
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
        with open("log", "a") as f:
            f.write(f"\n\nStep #{step}\n")
            if config["logs"]["log_thoughts"]:
                th = response.message.thinking
                if th:
                    f.write("\nThinking: \n" + th)
            if config["logs"]["log_output"]:
                con = response.message.content
                if con:
                    f.write("\nContent: \n" + con)
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
                    print(tc.function.name)
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


if __name__ == "__main__":
    if sys.stdin.isatty():
        prompt = input()
    else:
        prompt = sys.stdin.read()
    result: tuple = loop(prompt)
    print(result[0])
    if result[1] > 0:
        raise SystemExit(result[1])
