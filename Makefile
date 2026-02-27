# Makefile for AI Agent Assistant

.PHONY: install test test-report clean docs

# Installation and setup
install:
	@chmod +x install.sh
	@./install.sh

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
	@.venv/bin/python main.py --docs

# Launch the Streamlit UI
run-ui:
	@echo "Launching AI Agent Assistant UI..."
	@.venv/bin/streamlit run app.py

