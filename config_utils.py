import os

def get_config_value(key, default):
    """Retrieves a value from .config if it exists using exact key matching."""
    if os.path.exists(".config"):
        with open(".config", "r") as f:
            for line in f:
                # Strip whitespace and skip comments/empty lines
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("#"):
                    continue
                
                if "=" in clean_line:
                    k, v = clean_line.split("=", 1)
                    if k.strip() == key:
                        val = v.strip()
                        # Automatically set HF_TOKEN in environment for HuggingFace Hub
                        if key == "HF_TOKEN" and val and "your_huggingface_token" not in val:
                            os.environ["HF_TOKEN"] = val
                        return val
    return default
