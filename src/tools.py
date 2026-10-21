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
    """This is a tool for interacting with the filesystem and executing various commands, with available commands in $PATH."""
    return executor(script)


available_functions = {f.__name__: f for f in (run_script, end_loop, describe)}
tools = list(available_functions.values())
