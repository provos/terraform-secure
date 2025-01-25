import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tfsec.analyze import SecurityAnalysis, SecurityIssue, analyze_changes
from tfsec.llm_interface import LLMInterface


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.sample_changes = {
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

        self.sample_analysis = SecurityAnalysis(
            issues=[
                SecurityIssue(
                    severity="HIGH",
                    resource="google_compute_firewall.allow-http-https",
                    issue="Overly permissive firewall rule",
                    explanation="The firewall rule has been modified to allow access from any IP (0.0.0.0/0) instead of the previous restricted range (10.0.0.0/8).",
                    recommendation="Restrict the source IP range to only necessary networks. Avoid using 0.0.0.0/0 unless absolutely required."
                )
            ],
            summary="Found 1 HIGH severity security issue related to firewall rules."
        )

    @patch('tfsec.llm_interface.LLMInterface')
    def test_analyze_changes(self, mock_llm_class):
        # Configure mock LLM
        mock_llm = MagicMock()
        mock_llm.generate_pydantic.return_value = self.sample_analysis
        mock_llm_class.return_value = mock_llm

        # Run analysis
        analysis = analyze_changes(mock_llm, self.sample_changes)

        # Verify LLM was called correctly
        mock_llm.generate_pydantic.assert_called_once()
        call_args = mock_llm.generate_pydantic.call_args
        self.assertEqual(call_args[1]['temperature'], 0.2)

        # Verify analysis results
        self.assertIsInstance(analysis, SecurityAnalysis)
        self.assertEqual(len(analysis.issues), 1)
        self.assertEqual(analysis.issues[0].severity, "HIGH")
        self.assertEqual(analysis.issues[0].resource, "google_compute_firewall.allow-http-https")

    @patch('tfsec.analyze.llm_from_config')
    @patch('tfsec.analyze.run_terraform_plan')
    def test_main_function(self, mock_run_plan, mock_llm_from_config):
        # Configure mocks
        mock_llm = MagicMock()
        mock_llm.generate_pydantic.return_value = self.sample_analysis
        mock_llm_from_config.return_value = mock_llm

        mock_run_plan.return_value = MagicMock(
            error=None,
            json_plan={
                "resource_changes": [{
                    "address": "google_compute_firewall.allow-http-https",
                    "type": "google_compute_firewall",
                    "name": "allow-http-https",
                    "change": {
                        "before": {"source_ranges": ["10.0.0.0/8"]},
                        "after": {"source_ranges": ["0.0.0.0/0"]},
                        "actions": ["update"]
                    }
                }]
            }
        )

        # Test main function with arguments
        with patch('sys.argv', ['analyze.py', '/fake/dir', '--provider', 'openai', '--model', 'gpt-4']):
            from tfsec.analyze import main
            return_code = main()

            # Verify LLM configuration
            mock_llm_from_config.assert_called_once_with(
                provider='openai',
                model_name='gpt-4',
                use_cache=True
            )

            # Verify return code
            self.assertEqual(return_code, 0)

    @patch('tfsec.analyze.llm_from_config')
    @patch('tfsec.analyze.run_terraform_plan')
    def test_main_function_no_changes(self, mock_run_plan, mock_llm_from_config):
        # Configure mock to return no changes
        mock_run_plan.return_value = MagicMock(
            error=None,
            json_plan={"resource_changes": []}
        )

        # Test main function
        with patch('sys.argv', ['analyze.py', '/fake/dir']):
            from tfsec.analyze import main
            return_code = main()

            # Verify LLM was not called
            mock_llm_from_config.assert_called_once()
            self.assertEqual(return_code, 0)

    @patch('tfsec.analyze.llm_from_config')
    @patch('tfsec.analyze.run_terraform_plan')
    def test_main_function_error(self, mock_run_plan, mock_llm_from_config):
        # Configure mock to return an error
        mock_run_plan.return_value = MagicMock(
            error="Terraform initialization failed",
            json_plan=None
        )

        # Test main function
        with patch('sys.argv', ['analyze.py', '/fake/dir']):
            from tfsec.analyze import main
            return_code = main()

            # Verify error handling
            self.assertEqual(return_code, 1)
            mock_llm_from_config.assert_called_once()


if __name__ == '__main__':
    unittest.main()
