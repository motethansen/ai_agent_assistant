import os

def get_config_value(key, default):
    """Retrieves a value from .config if it exists."""
    if os.path.exists(".config"):
        with open(".config", "r") as f:
            for line in f:
                if f"{key}=" in line:
                    val = line.split("=")[1].strip()
                    # Automatically set HF_TOKEN in environment for HuggingFace Hub
                    if key == "HF_TOKEN" and val and "your_huggingface_token" not in val:
                        os.environ["HF_TOKEN"] = val
                    return val
    return default
