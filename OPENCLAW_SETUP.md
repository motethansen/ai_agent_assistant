# OpenClaw Integration: Multiple Online LLMs

OpenClaw is designed to be a local-first gateway that can route requests to multiple online and local LLMs. By default, it uses a configuration file to manage models and API keys.

## 1. Setting up Models and API Keys

OpenClaw's configuration is typically stored in `~/.openclaw/openclaw.json`. You can manage your models using the CLI:

### Adding an OpenAI Model
To add OpenAI models, set your API key and then configure the model in `openclaw.json`:

```bash
export OPENAI_API_KEY="your_openai_api_key_here"
# OpenClaw will detect the environment variable, or you can add it to the config
```

### Adding an Anthropic Model (Recommended)
OpenClaw strongly recommends Anthropic for its long-context capabilities:

```bash
export ANTHROPIC_API_KEY="your_anthropic_api_key_here"
```

## 2. Configuring `openclaw.json`

You can manually edit `~/.openclaw/openclaw.json` to define which models are available and which one is the default.

Example `openclaw.json`:

```json
{
  "agent": {
    "model": "anthropic/claude-3-5-sonnet",
    "fallbackModels": ["openai/gpt-4o", "ollama/qwen2.5:7b"]
  },
  "models": {
    "openai/gpt-4o": {
      "apiKey": "sk-..."
    },
    "anthropic/claude-3-5-sonnet": {
      "apiKey": "sk-ant-..."
    }
  }
}
```

## 3. Model Routing and Failover

OpenClaw supports automatic failover. If your primary model (e.g., Anthropic) is down or hits a rate limit, it can automatically switch to a fallback model (e.g., OpenAI or a local Ollama model).

To configure this, use the `fallbackModels` array in your `openclaw.json`.

## 4. Using the Onboarding Wizard

The easiest way to configure multiple LLMs is via the interactive onboarding wizard:

```bash
openclaw onboard
```

The wizard will guide you through:
- Setting up your workspace.
- Adding API keys for various providers.
- Selecting your default models.
- Installing the daemon to keep the gateway running in the background.

## 5. Integrating with this AI Assistant

Once OpenClaw is running (on port 18789 by default), this AI Assistant will automatically route requests to it if `ENABLE_OPENCLAW=true` is set in your `.config` file.

You can specify which OpenClaw model to use by setting `OPENCLAW_MODEL` in `.config`:

```ini
ENABLE_OPENCLAW=true
OPENCLAW_MODEL=gpt-4o
OPENCLAW_ENDPOINT=http://localhost:18789/v1
```
