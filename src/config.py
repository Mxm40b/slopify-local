from pathlib import Path

import tomllib

# parent two times to get out of src/ into project root
PROJECT_DIR = Path(__file__).resolve().parent.parent

with open("config/slopify/slopify.toml") as f:
    config = tomllib.loads(f.read())
