from dataclasses import dataclass
from pathlib import Path
import subprocess
import json
from typing import Optional, Dict, Any


@dataclass
class TerraformPlanResult:
    stdout: str
    stderr: str
    json_plan: Optional[Dict[str, Any]]
    return_code: int
    error: Optional[str] = None


def run_terraform_plan(directory: Path) -> TerraformPlanResult:
    """
    Run terraform plan in the specified directory and capture the output in JSON format.
    
    Args:
        directory: Path to the directory containing terraform configuration
        
    Returns:
        TerraformPlanResult containing stdout, stderr, and parsed JSON plan
    """
    try:
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
