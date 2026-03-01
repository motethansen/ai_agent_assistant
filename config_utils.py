import os

def get_config_value(key, default):
    """Retrieves a value from .config if it exists."""
    if os.path.exists(".config"):
        with open(".config", "r") as f:
            for line in f:
                if f"{key}=" in line:
                    return line.split("=")[1].strip()
    return default
