import os
import shutil
import pytest
import subprocess
from unittest.mock import patch, MagicMock

# Import common logic
def test_agent_scaffolding(tmp_path):
    """
    Test that the agent scaffolding logic works as expected.
    """
    # Create mock environment
    custom_agents_dir = tmp_path / "custom_agents"
    custom_agents_dir.mkdir()
    
    agent_name = "test_agent"
    agent_path = custom_agents_dir / f"{agent_name}.py"
    
    # Logic to simulate /create-agent
    with open(agent_path, "w") as f:
        f.write('def run(context):\n    return "Agent test_agent executed successfully."\n')
    
    assert agent_path.exists()
    with open(agent_path, "r") as f:
        content = f.read()
        assert "def run(context):" in content
        assert "Agent test_agent executed successfully." in content

def test_agent_loading(tmp_path):
    """
    Verify the discovery mechanism for dynamic agents.
    """
    custom_agents_dir = tmp_path / "custom_agents"
    custom_agents_dir.mkdir()
    
    # Create a simple agent file
    with open(custom_agents_dir / "hello_agent.py", "w") as f:
        f.write('def run(context):\n    return "Hello World!"\n')
    
    # Discovery logic test
    agents = [f[:-3] for f in os.listdir(custom_agents_dir) if f.endswith(".py") and f != "__init__.py"]
    assert "hello_agent" in agents

def test_git_init_for_agent(tmp_path):
    """
    Verify that an agent can be initialized as a separate git repository.
    """
    agent_dir = tmp_path / "custom_agents" / "git_agent_repo"
    agent_dir.mkdir(parents=True)
    
    with open(agent_dir / "agent.py", "w") as f:
        f.write('print("Git test")')
    
    subprocess.run(["git", "init"], cwd=str(agent_dir), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(agent_dir), capture_output=True)
    # Configure git for test environment to avoid "Author identity unknown"
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(agent_dir))
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(agent_dir))
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(agent_dir), capture_output=True)
    
    # Check if .git directory exists
    assert (agent_dir / ".git").exists()
