from config import PROJECT_DIR
from executor import *


def end_loop(end_message: str, successful: bool):
    """This is the tool that you call to end the loop, once you're confident either the task is finished or that it can't be finished with the available tools, by you.
    Provide your final answers through end_message, even if they are failures (in which case you should say why). Assume that anything you say prior to this tool call is not read by the user.
    end_message is the text that you want to write for the user once you have finished the task to inform them of what you did, or what you couldn't do, without too much detail. the successful flag is for you to tell the user whether you succeeded or failed (or think you won't succeed)."""


def describe(message: str) -> str:
    """This is a tool for describing what you have done, figured out, or don't know yet."""
    with open("log", "a") as f:
        f.write(f"Description:\n{message}\n")
    return "Wrote the description provided to the log file"


def run_script(script: str):
    """This is a tool for interacting with the filesystem and executing various commands, with available commands in $PATH.
    You are allowed to run commands without even knowing what arguments they expect. Learn by making mistakes.
    The output is trimmed, in case you don't understand the output of your commands."""
    return executor(script)


def request(request_message: str, summary: str) -> None:
    """This is a tool to ask for access to more commands, or a change in the environment.
    Because of how the harness is made, you need to provide a summary/handoff report of what happened up to now in summary;
    Once the user has changed the environment (or not), a new agent will have access to that summary to continue."""
    print("\nThe model has requested a change to the environment:")
    print(f"'{request_message}'\n")
    with open(f"{PROJECT_DIR}/summary.txt", "w") as f:
        f.write(summary)
    with open(f"{PROJECT_DIR}/log", "a") as f:
        f.write("\n\nThe agent requested a new tool.\n")


def summarize(summary: str) -> None:
    """This is a tool for you to summarize everything that you have done so far (handoff report)
    for a new agent with a clean chat log to pick up the task with exactly the same prompt."""
    with open(f"{PROJECT_DIR}/summary.txt", "w") as f:
        f.write(summary)
    with open(f"{PROJECT_DIR}/log", "a") as f:
        f.write("\n\nThe agent summarized its work so far.\n")


usual_available_functions = {
    f.__name__: f for f in (run_script, end_loop, describe, request, summarize)
}
usual_tools = list(usual_available_functions.values())
end_available_functions = {f.__name__: f for f in (end_loop, summarize)}
end_tools = list(usual_available_functions.values())
