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

from tfsec.llm_interface import LLMInterface
from tfsec.llm_config import llm_from_config
from tfsec.parse import run_terraform_plan, create_resource_changes_dict


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


SECURITY_ANALYSIS_PROMPT = dedent("""You are a cloud security expert specializing in Terraform infrastructure-as-code security analysis. Your task is to thoroughly analyze the security implications of proposed Terraform infrastructure changes.

Please examine the following Terraform plan output, represented in JSON format, which describes the intended modifications to the existing infrastructure:

{changes}

**Your analysis should be comprehensive and cover, but not be limited to, the following areas:**

1.  **Network Security:**
    *   **Firewall Rules:** Analyze changes to `google_compute_firewall`, `aws_security_group`, `azurerm_network_security_group`, or equivalent resources. Identify any new, modified, or removed rules, focusing on:
        *   **Ingress and Egress Rules:** Scrutinize changes to allowed ports, protocols (TCP, UDP, ICMP), source/destination IP ranges (CIDR blocks), security groups, and source/destination tags.
        *   **Overly Permissive Rules:** Flag rules that allow access from overly broad sources (e.g., `0.0.0.0/0`) or to sensitive ports (e.g., SSH, RDP, database ports).
    *   **Network Exposure:** Assess changes to `google_compute_instance`, `aws_instance`, `azurerm_virtual_machine`, or equivalent resources that might expose instances directly to the public internet (e.g., changes to public IP assignment, network interfaces).
    *   **Load Balancers and Application Gateways:** Analyze changes to load balancer configurations that might impact traffic routing, SSL/TLS termination, and security policies.
    *   **VPNs and Direct Connections:** Identify changes related to VPN gateways, virtual private gateways, or direct connect configurations that might affect secure connectivity.
    *   **DNS and Routing:** Identify changes to DNS settings or routing tables that might expose internal resources or direct traffic to untrusted destinations.

2.  **Identity and Access Management (IAM):**
    *   **User and Role Management:** Analyze changes to IAM users, roles, groups, and policies (e.g., `google_service_account`, `aws_iam_role`, `azurerm_role_definition`, or changes to `metadata.enable-oslogin`). Identify new or modified permissions, particularly those that grant excessive privileges (e.g., administrator access).
    *   **Service Accounts/Roles:** Examine changes to service accounts or roles used by applications and services. Assess whether their permissions adhere to the principle of least privilege.
    *   **Authentication Mechanisms:** Identify changes that impact authentication methods, such as modifications to SSH key configurations, or enabling/disabling password-based authentication.

3.  **Data Security:**
    *   **Storage Encryption:** Analyze changes to storage services (e.g., `google_storage_bucket`, `aws_s3_bucket`, `azurerm_storage_account`) that might affect encryption at rest settings.
    *   **Database Security:** Scrutinize changes to database instances (e.g., `google_sql_database_instance`, `aws_db_instance`, `azurerm_sql_database`) related to security groups, authentication, and encryption.
    *   **Key Management:** Examine changes to key management services (e.g., `google_kms_crypto_key`, `aws_kms_key`, `azurerm_key_vault_key`) that might impact encryption key usage and security.
    *   **Secrets Management:** Identify changes to secrets stored in services like `google_secret_manager_secret`, `aws_secretsmanager_secret`, `azurerm_key_vault_secret`. Assess whether these changes are done securely.

4.  **Resource Exposure and Hardening:**
    *   **Public Access:** Identify any changes that might make resources publicly accessible that should not be (e.g., changes to storage bucket ACLs, database instance visibility).
    *   **OS Hardening:** Review changes related to OS-level security configurations, such as disabling unnecessary services, enabling security auditing, and applying security patches.

5.  **Compliance and Best Practices:**
    *   **Compliance Standards:** Assess whether the changes comply with relevant industry standards and regulations (e.g., PCI DSS, HIPAA, SOC 2, GDPR, CIS Benchmarks).
    *   **Principle of Least Privilege:** Evaluate whether all access granted is strictly necessary and follows the principle of least privilege.
    *   **Security Groups vs. Network ACLs:** Analyze whether the use of security groups and network ACLs is appropriate and layered effectively.

**For each identified security-relevant change or concern:**

1.  **Severity Assessment:** Classify the severity of the risk as **Critical, High, Medium, or Low**.
2.  **Detailed Explanation:** Provide a clear and concise explanation of the security implications. Describe the potential impact and attack vectors.
3.  **Specific Recommendations:** Offer actionable recommendations to mitigate the identified risks. These should include specific configuration changes or alternative approaches.

Format your response according to the provided schema, including a markdown summary.
Consider both direct and indirect security impacts of the changes.
""").strip()


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
