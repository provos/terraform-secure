"""Terraform Security Analysis Module

This module analyzes Terraform plan changes for security implications using LLMs.
It identifies potentially risky changes and provides security recommendations.
"""

import argparse
import json
from textwrap import dedent
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from llm_interface import LLMInterface, llm_from_config
from tfsec.parse import run_terraform_plan, create_resource_changes_dict, load_plan_result


class SecurityIssue(BaseModel):
    """Represents a single security issue found in the changes."""
    severity: str = Field(..., description="Severity level: HIGH, MEDIUM, or LOW")
    resource: str = Field(..., description="The Terraform resource identifier")
    issue: str = Field(..., description="Brief description of the security issue")
    explanation: str = Field(..., description="Detailed explanation of the security implications")
    recommendation: str = Field(..., description="Recommended remediation steps")


class SecurityAnalysis(BaseModel):
    """Contains the full security analysis of Terraform changes."""
    issues: List[SecurityIssue] = Field(
        default_factory=list,
        description="List of identified security issues"
    )
    summary: str = Field(
        "",
        description="Overall summary of the security analysis in markdown format"
    )


SECURITY_ANALYSIS_PROMPT = dedent("""You are a cloud security expert specializing in Terraform infrastructure-as-code security analysis. Your task is to thoroughly analyze the security implications of proposed Terraform infrastructure changes and structure your findings according to the provided schema.

Please examine the following Terraform plan output and identify potential security issues:

{changes}

For each security issue you find:
1. Create a SecurityIssue object with:
   - severity: Critical, High, Medium, or Low
   - resource: The specific Terraform resource identifier
   - issue: A brief (1-2 sentence) description of the security concern
   - explanation: A detailed explanation of the security implications and potential risks
   - recommendation: Specific, actionable steps to remediate the issue

The summary field should provide a brief overview that includes:
1. The total number of issues found by severity
2. The highest-risk areas that need immediate attention
3. A general assessment of the overall security impact
Keep the summary concise (3-5 sentences) as the details should be in the issues.

Consider these key areas in your analysis:
- Network security (firewall rules, network exposure, load balancers)
- Identity and access management (IAM roles, service accounts, permissions)
- Data security (encryption, database security, key management)
- Resource exposure (public accessibility, OS hardening)
- Compliance with security best practices and standards

Format your response according to the SecurityAnalysis schema, with individual findings as SecurityIssue objects in the issues list, and a brief executive summary in the summary field.""").strip()


def analyze_changes(llm: LLMInterface, changes: Dict) -> Optional[SecurityAnalysis]:
    """
    Analyze Terraform changes for security implications using an LLM.
    
    Args:
        llm: LLMInterface instance for generating security analysis
        changes: Dictionary of Terraform resource changes
        
    Returns:
        SecurityAnalysis object containing identified issues and recommendations
    """
    # Format changes for the prompt
    changes_str = json.dumps(changes, indent=2)
    
    # Generate security analysis using the LLM
    analysis = llm.generate_pydantic(
        prompt_template=SECURITY_ANALYSIS_PROMPT,
        output_schema=SecurityAnalysis,
        changes=changes_str,
        temperature=0.2  # Lower temperature for more focused security analysis
    )
    
    return analysis


def main():
    parser = argparse.ArgumentParser(description='Analyze Terraform changes for security implications')
    parser.add_argument('--directory', type=Path, help='Directory containing Terraform configuration')
    parser.add_argument('--state', type=Path, help='Path to Terraform state file')
    parser.add_argument('--plan-file', type=Path, help='Read analysis from saved plan file instead of running terraform')
    parser.add_argument('--provider', default='ollama', choices=['ollama', 'openai', 'anthropic'],
                       help='LLM provider to use')
    parser.add_argument('--model', default='phi4:latest', help='Model name to use')
    
    args = parser.parse_args()

    if not args.directory and not args.plan_file:
        parser.error("Either --directory or --plan-file must be specified")

    # Create LLM interface
    llm = llm_from_config(
        provider=args.provider,
        model_name=args.model,
        use_cache=True
    )
    
    # Get Terraform changes
    if args.plan_file:
        result = load_plan_result(args.plan_file)
    else:
        result = run_terraform_plan(args.directory, args.state)

    if result.error:
        print(f"Error: {result.error}")
        return 1
        
    if not result.json_plan:
        print("No changes to analyze")
        return 0
        
    # Extract and analyze changes
    changes = create_resource_changes_dict(result.json_plan)
    if not changes:
        print("No changes detected")
        return 0
        
    # Perform security analysis
    analysis = analyze_changes(llm, {"changes": changes})
    if not analysis:
        print("Failed to generate security analysis")
        return 1
        
    # Print results
    print("\nSecurity Analysis Summary")
    print("========================\n")
    print(analysis.summary)
    
    if analysis.issues:
        print("\nDetailed Security Issues")
        print("=======================\n")
        for issue in analysis.issues:
            print(f"Severity: {issue.severity}")
            print(f"Resource: {issue.resource}")
            print(f"Issue: {issue.issue}")
            print("\nExplanation:")
            print(issue.explanation)
            print("\nRecommendation:")
            print(issue.recommendation)
            print("\n---\n")
    
    return 0


if __name__ == "__main__":
    exit(main())
