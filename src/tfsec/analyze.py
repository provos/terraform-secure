"""Terraform Security Analysis Module

This module analyzes Terraform plan changes for security implications using LLMs.
It identifies potentially risky changes and provides security recommendations.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from .llm_interface import LLMInterface
from .llm_config import llm_from_config
from .parse import run_terraform_plan, create_resource_changes_dict


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


SECURITY_ANALYSIS_PROMPT = """You are a security expert analyzing Terraform infrastructure changes.
Please analyze the following Terraform resource changes for security implications:

{changes}

Focus on:
1. Network security (firewall rules, open ports, CIDR ranges)
2. Access controls and permissions
3. Resource exposure to the internet
4. Security best practices
5. Compliance concerns

For each security-relevant change:
1. Assess the severity
2. Explain the security implications
3. Provide specific recommendations

Format your response according to the provided schema, including a markdown summary.
Consider both direct and indirect security impacts of the changes.
"""


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
    parser.add_argument('directory', type=Path, help='Directory containing Terraform configuration')
    parser.add_argument('--state', type=Path, help='Path to Terraform state file')
    parser.add_argument('--provider', default='ollama', choices=['ollama', 'openai', 'anthropic'],
                       help='LLM provider to use')
    parser.add_argument('--model', default='phi4:latest', help='Model name to use')
    
    args = parser.parse_args()

    # Create LLM interface
    llm = llm_from_config(
        provider=args.provider,
        model_name=args.model,
        use_cache=True
    )
    
    # Get Terraform changes
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
