# Makefile for AI Agent Assistant

.PHONY: install test test-report clean docs run run-chat run-ui stats cron upgrade

# Installation and setup
install:
	@chmod +x install.sh
	@./install.sh

setup:
	@echo "Launching Setup Wizard..."
	@.venv/bin/streamlit run setup_wizard.py

# Interactive chat (default daily use)
run:
	@./run.sh

# Background file-watcher daemon
service:
	@./service.sh start

service-stop:
	@./service.sh stop

service-status:
	@./service.sh status

service-install:
	@./service.sh install

# Launch the Streamlit UI
run-ui:
	@echo "Launching AI Agent Assistant UI..."
	@.venv/bin/streamlit run app.py

# Run all tests using pytest
test:
	@echo "Running tests..."
	@PYTHONPATH=. .venv/bin/pytest tests/

# Run tests and generate an HTML report (requires pytest-html)
test-report:
	@echo "Running tests and generating HTML report..."
	@PYTHONPATH=. .venv/bin/pytest tests/ --html=reports/test_report.html --self-contained-html

# Clean up temporary files
clean:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@rm -rf reports/

# Display CLI-based documentation
docs:
	@.venv/bin/python3 main.py --docs

# Display statistics and configuration
stats:
	@.venv/bin/python3 main.py --stats

# Other management commands
cron:
	@./install.sh cron

upgrade:
	@./install.sh upgrade
