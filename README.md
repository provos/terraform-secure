# Terraform Plan Security Analyzer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

This tool analyzes Terraform plan changes for security implications using Large Language Models (LLMs). It identifies potentially risky changes and provides security recommendations by examining the differences between current and planned infrastructure states.

## Features

* **LLM-Powered Analysis:** Uses advanced language models to provide contextual security analysis
* **Comprehensive Security Review:** Analyzes multiple security aspects including:
  * Network Security (firewall rules, network exposure)
  * Identity and Access Management (IAM)
  * Data Security (encryption, storage)
  * Resource Exposure and Hardening
  * Compliance and Best Practices
* **Flexible LLM Support:** Works with multiple LLM providers (Ollama, OpenAI, Anthropic)
* **Detailed Reports:** Generates comprehensive security analysis with:
  * Severity ratings for each issue
  * Detailed explanations of security implications
  * Specific recommendations for remediation

## Installation

1. Install Poetry if you haven't already:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Clone the repository and install dependencies:
```bash
git clone <repository-url>
cd terraform-secure
poetry install
```

## Usage

You can use this tool in two ways:

### 1. Direct Analysis with Terraform

Basic usage with direct Terraform execution:
```bash
# Using Poetry
poetry run python -m tfsec.analyze <terraform_directory> --state <state_file>

# Using PYTHONPATH
PYTHONPATH=src python -m tfsec.analyze <terraform_directory> --state <state_file>
```

### 2. Analysis from Saved Plan File

To avoid re-running Terraform commands repeatedly, you can save the plan to a file first:
```bash
# Save the plan to a JSON file
python src/tfsec/parse.py --state examples/terraform.tfstate examples/insecure-firewall/ --output examples/tf-insecure-diff.json

# Analyze the saved plan file
PYTHONPATH=src python -m tfsec.analyze --plan-file examples/tf-insecure-diff.json
```

This approach is useful for:
- CI/CD pipelines where you want to separate plan generation from analysis
- Sharing plans with team members for review
- Analyzing the same plan multiple times with different settings

Options:
* `--provider`: LLM provider to use (ollama, openai, anthropic) [default: ollama]
* `--model`: Model name to use [default: phi4:latest]
* `--state`: Path to Terraform state file (when running with Terraform)
* `--plan-file`: Path to saved plan file (when analyzing without Terraform)
* `terraform_directory`: Directory containing Terraform configuration

Example:
```bash
PYTHONPATH=src python -m tfsec.analyze --state examples/terraform.tfstate examples/insecure-firewall/
```

## Requirements

* Python 3.7+
* Poetry for dependency management
* Terraform CLI installed and in PATH
* Access to an LLM provider (Ollama, OpenAI, or Anthropic)

## Output Format

The tool provides:
1. A high-level security analysis summary
2. Detailed list of security issues including:
   * Severity level
   * Affected resource
   * Issue description
   * Detailed security implications
   * Recommended remediation steps

## Why This Is Important

*   **Prevent Security Misconfigurations:** Proactively identify and address security risks before they are deployed to your infrastructure.
*   **Enforce Security Policies:** Ensure that all Terraform changes adhere to your organization's security standards and best practices.
*   **Reduce Manual Review Effort:** Automate a significant portion of the security review process, freeing up security teams to focus on more complex issues.
*   **Shift-Left Security:** Integrate security checks early in the development lifecycle, making it easier and cheaper to fix issues.
*   **Improve Auditability:** Maintain a record of all security-related changes detected and addressed during the Terraform deployment process.

## How to Use

1.  **Generate Terraform Plan:**
    ```bash
    terraform plan -out=tfplan
    terraform show -json tfplan > tfplan.json
    ```

2.  **Run the Analyzer:**
    ```bash
    # Example using a Python script (analyzer.py - to be developed):
    python analyzer.py --plan tfplan.json --rules rules.yaml
    ```
    Or potentially:
    ```bash
    # Example using a shell script:
    ./analyze_plan.sh tfplan.json
    ```

3.  **Review the Report:**
    The analyzer will generate a report (e.g., `security_report.txt` or `security_report.json`) detailing any potential security issues.

4.  **Integrate with CI/CD:**
    Add a step to your CI/CD pipeline to execute the analyzer after the `terraform plan` step.  Configure the pipeline to fail if the analyzer detects any critical issues. (See "CI/CD Integration" section below for more details)

## Example Report (Conceptual)