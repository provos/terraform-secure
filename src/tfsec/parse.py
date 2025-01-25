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


def run_terraform_plan(directory: Path, state_file: Optional[Path] = None) -> TerraformPlanResult:
    """
    Run terraform plan in the specified directory and capture the output in JSON format.
    
    Args:
        directory: Path to the directory containing terraform configuration
        state_file: Optional path to a terraform state file to use
        
    Returns:
        TerraformPlanResult containing stdout, stderr, and parsed JSON plan
    """
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

def main():
    import sys
    import json
    import argparse

    parser = argparse.ArgumentParser(description='Parse Terraform plan output')
    parser.add_argument('directory', type=Path, help='Directory containing Terraform configuration')
    parser.add_argument('--state', type=Path, help='Path to Terraform state file to use')
    
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a valid directory")
        sys.exit(1)

    if args.state and not args.state.exists():
        print(f"Error: State file {args.state} does not exist")
        sys.exit(1)

    result = run_terraform_plan(args.directory, args.state)
    
    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        print(f"Stderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    if result.json_plan:
        changes = {}
        for resource in result.json_plan.get("resource_changes", []):
            resource_changes = extract_changes(resource.get("change", {}))
            if resource_changes:
                changes[resource["address"]] = {
                    "type": resource.get("type", ""),
                    "name": resource.get("name", ""),
                    "action": resource["change"].get("actions", []),
                    "changes": resource_changes
                }

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
