"""Terraform Plan Parser Module

This module provides functionality to analyze Terraform plan changes by comparing
against an existing state file. It requires an existing Terraform state file to
generate meaningful diffs, as Terraform uses this state to determine what changes
are needed.

Requirements:
    - Python 3.7+
    - Terraform CLI installed and in PATH
    - An existing Terraform state file for comparison

Usage:
    python parse.py <terraform_directory> --state <path_to_state_file>

Example:
    python parse.py ./my-terraform-config --state ./terraform.tfstate

The module works by:
1. Copying the provided state file to the target directory
2. Running terraform init to initialize the configuration
3. Executing terraform plan to generate a plan
4. Converting the plan to JSON format
5. Analyzing changes between the existing state and planned state
6. Reporting differences in resources

Output Format:
    {
      "changes": {
        "google_compute_firewall.allow-http-https": {
          "type": "google_compute_firewall",
          "name": "allow-http-https",
          "action": ["update"],
          "changes": {
            "source_ranges": {
              "before": ["10.0.0.0/8"],
              "after": ["0.0.0.0/0"]
            }
          }
        }
      }
    }

Important Notes:
    1. State File Requirement: An existing state file is crucial for generating
       meaningful diffs. Without it, Terraform treats everything as new resources.
    2. State File Handling: The module temporarily copies the state file to the
       target directory and removes it after planning.
    3. Security: Ensure the state file contains no sensitive information, as it
       may be logged in the diff output.

Example Use Cases:
    1. Security Auditing:
       python parse.py ./firewall-rules --state prod.tfstate
    2. Change Validation:
       python parse.py ./network-config --state current.tfstate

Error Handling:
    The module handles several error conditions:
    - Missing state file
    - Invalid Terraform configuration
    - JSON parsing errors
    - Terraform execution failures
    Error messages are written to stderr with appropriate exit codes.
"""

from dataclasses import dataclass
from pathlib import Path
import subprocess
import json
import shutil
from typing import Optional, Dict, Any


@dataclass
class TerraformPlanResult:
    stdout: str
    stderr: str
    json_plan: Optional[Dict[str, Any]]
    return_code: int
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary for serialization."""
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "json_plan": self.json_plan,
            "return_code": self.return_code,
            "error": self.error
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TerraformPlanResult':
        """Create a TerraformPlanResult from a dictionary."""
        return cls(
            stdout=data["stdout"],
            stderr=data["stderr"],
            json_plan=data["json_plan"],
            return_code=data["return_code"],
            error=data.get("error")
        )

def save_plan_result(result: TerraformPlanResult, output_file: Path) -> None:
    """Save TerraformPlanResult to a JSON file."""
    with open(output_file, 'w') as f:
        json.dump(result.to_dict(), f, indent=2)

def load_plan_result(input_file: Path) -> TerraformPlanResult:
    """Load TerraformPlanResult from a JSON file."""
    with open(input_file) as f:
        data = json.load(f)
    return TerraformPlanResult.from_dict(data)

def run_terraform_plan(directory: Path, state_file: Optional[Path] = None, output_file: Optional[Path] = None) -> TerraformPlanResult:
    """Run terraform plan in the specified directory and capture the output in JSON format."""
    result = _run_terraform_plan(directory, state_file)
    if output_file and result:
        save_plan_result(result, output_file)
    return result

def _run_terraform_plan(directory: Path, state_file: Optional[Path] = None) -> TerraformPlanResult:
    copied_state = None
    try:
        # Copy state file if provided
        if state_file and state_file.exists():
            copied_state = directory / "terraform.tfstate"
            shutil.copy2(state_file, copied_state)

        # Initialize terraform
        init_process = subprocess.run(
            ["terraform", "init"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )

        # Run terraform plan with JSON output
        plan_process = subprocess.run(
            ["terraform", "plan", "-out=tfplan", "-detailed-exitcode"],
            cwd=directory,
            capture_output=True,
            text=True
        )

        # Convert plan to JSON
        show_process = subprocess.run(
            ["terraform", "show", "-json", "tfplan"],
            cwd=directory,
            capture_output=True,
            text=True
        )

        json_plan = None
        if show_process.returncode == 0:
            try:
                json_plan = json.loads(show_process.stdout)
            except json.JSONDecodeError as e:
                return TerraformPlanResult(
                    stdout=plan_process.stdout,
                    stderr=plan_process.stderr,
                    json_plan=None,
                    return_code=1,
                    error=f"Failed to parse JSON: {str(e)}"
                )

        return TerraformPlanResult(
            stdout=plan_process.stdout,
            stderr=plan_process.stderr,
            json_plan=json_plan,
            return_code=plan_process.returncode
        )

    except subprocess.CalledProcessError as e:
        return TerraformPlanResult(
            stdout=e.stdout if hasattr(e, 'stdout') else "",
            stderr=e.stderr if hasattr(e, 'stderr') else "",
            json_plan=None,
            return_code=e.returncode,
            error=str(e)
        )
    finally:
        # Cleanup copied state file
        if copied_state and copied_state.exists():
            copied_state.unlink()


def extract_changes(resource_change):
    """Extract differences between before and after states."""
    if not resource_change:
        return None
        
    before = resource_change.get("before", {})
    after = resource_change.get("after", {})
    actions = resource_change.get("actions", [])
    
    # Skip if no actual change
    if "no-op" in actions:
        return None
        
    # Compare before and after directly
    changes = {}
    if before is not None and after is not None:
        all_keys = set(before.keys()) | set(after.keys())
        for key in all_keys:
            before_value = before.get(key)
            after_value = after.get(key)
            if before_value != after_value:
                changes[key] = {
                    "before": before_value,
                    "after": after_value
                }
                
    return changes if changes else None

def create_resource_changes_dict(json_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a dictionary of resource changes from terraform plan JSON.
    
    Args:
        json_plan: Dictionary containing terraform plan JSON
        
    Returns:
        Dictionary containing resource changes
    """
    changes = {}
    for resource in json_plan.get("resource_changes", []):
        resource_changes = extract_changes(resource.get("change", {}))
        if resource_changes:
            changes[resource["address"]] = {
                "type": resource.get("type", ""),
                "name": resource.get("name", ""),
                "action": resource["change"].get("actions", []),
                "changes": resource_changes
            }
    return changes

def main():
    import sys
    import json
    import argparse

    parser = argparse.ArgumentParser(description='Parse Terraform plan output')
    parser.add_argument('directory', type=Path, help='Directory containing Terraform configuration')
    parser.add_argument('--state', type=Path, help='Path to Terraform state file to use')
    parser.add_argument('--output', type=Path, help='Save plan result to JSON file')
    
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a valid directory")
        sys.exit(1)

    if args.state and not args.state.exists():
        print(f"Error: State file {args.state} does not exist")
        sys.exit(1)

    result = run_terraform_plan(args.directory, args.state, args.output)
    
    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        print(f"Stderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    if result.json_plan:
        changes = create_resource_changes_dict(result.json_plan)
        if changes:
            print(json.dumps({"changes": changes}, indent=2))
        else:
            print("No changes detected")
    else:
        print("No JSON plan was generated", file=sys.stderr)
        print(f"Stdout: {result.stdout}", file=sys.stderr)
        print(f"Stderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
