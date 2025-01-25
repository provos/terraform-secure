import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import tfsec.parse
from tfsec.parse import TerraformPlanResult, run_terraform_plan


class TestTerraformParse(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("/fake/terraform/dir")
        self.sample_json = {
            "format_version": "1.0",
            "planned_values": {"root_module": {"resources": []}},
        }

    @patch("tfsec.parse.subprocess.run")
    def test_successful_terraform_plan(self, mock_run):
        # Mock successful execution of all commands
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Init success", stderr=""),  # init
            MagicMock(returncode=0, stdout="Plan success", stderr=""),  # plan
            MagicMock(
                returncode=0, stdout=json.dumps(self.sample_json), stderr=""
            ),  # show
        ]

        result = run_terraform_plan(self.test_dir)

        self.assertEqual(result.return_code, 0)
        self.assertEqual(result.json_plan, self.sample_json)
        self.assertEqual(result.stdout, "Plan success")
        self.assertIsNone(result.error)

    @patch("tfsec.parse.subprocess.run")
    def test_terraform_init_failure(self, mock_run):
        # Mock terraform init failure
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["terraform", "init"],
            output="Init failed",
            stderr="Error initializing",
        )

        result = run_terraform_plan(self.test_dir)

        self.assertEqual(result.return_code, 1)
        self.assertIsNone(result.json_plan)
        self.assertIsNotNone(result.error)

    @patch("tfsec.parse.subprocess.run")
    def test_invalid_json_output(self, mock_run):
        # Mock successful commands but invalid JSON output
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Init success", stderr=""),  # init
            MagicMock(returncode=0, stdout="Plan success", stderr=""),  # plan
            MagicMock(returncode=0, stdout="Invalid JSON", stderr=""),  # show
        ]

        result = run_terraform_plan(self.test_dir)

        self.assertEqual(result.return_code, 1)
        self.assertIsNone(result.json_plan)
        self.assertTrue("Failed to parse JSON" in result.error)

    @patch("tfsec.parse.subprocess.run")
    def test_plan_with_changes(self, mock_run):
        # Mock terraform plan indicating changes (return code 2)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Init success", stderr=""),  # init
            MagicMock(returncode=2, stdout="Changes pending", stderr=""),  # plan
            MagicMock(
                returncode=0, stdout=json.dumps(self.sample_json), stderr=""
            ),  # show
        ]

        result = run_terraform_plan(self.test_dir)

        self.assertEqual(result.return_code, 2)
        self.assertEqual(result.stdout, "Changes pending")
        self.assertEqual(result.json_plan, self.sample_json)


if __name__ == "__main__":
    unittest.main()
