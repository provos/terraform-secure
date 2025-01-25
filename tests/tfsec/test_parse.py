import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from tfsec.parse import run_terraform_plan, extract_changes, create_resource_changes_dict


class TestTerraformParse(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("/fake/terraform/dir")
        self.sample_json = {
            "format_version": "1.0",
            "planned_values": {"root_module": {"resources": []}},
        }
        self.test_state_file = Path("/fake/terraform/state.tfstate")
        self.sample_resource_change = {
            "before": {
                "source_ranges": ["10.0.0.0/8"],
                "name": "test-firewall"
            },
            "after": {
                "source_ranges": ["0.0.0.0/0"],
                "name": "test-firewall"
            },
            "actions": ["update"]
        }

    @patch("tfsec.parse.shutil.copy2")
    @patch("tfsec.parse.subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.unlink")
    def test_plan_with_state_file(self, mock_unlink, mock_exists, mock_run, mock_copy):
        # Mock file operations
        mock_exists.return_value = True
        
        # Mock successful execution of all commands
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Init success", stderr=""),
            MagicMock(returncode=0, stdout="Plan success", stderr=""),
            MagicMock(returncode=0, stdout=json.dumps(self.sample_json), stderr="")
        ]

        result = run_terraform_plan(self.test_dir, self.test_state_file)

        # Verify state file was copied and cleaned up
        mock_copy.assert_called_once()
        mock_unlink.assert_called_once()
        self.assertEqual(result.return_code, 0)

    def test_extract_changes_with_updates(self):
        changes = extract_changes(self.sample_resource_change)
        
        self.assertIsNotNone(changes)
        self.assertIn("source_ranges", changes)
        self.assertEqual(changes["source_ranges"]["before"], ["10.0.0.0/8"])
        self.assertEqual(changes["source_ranges"]["after"], ["0.0.0.0/0"])

    def test_extract_changes_with_no_op(self):
        no_op_change = {
            "before": {"name": "test"},
            "after": {"name": "test"},
            "actions": ["no-op"]
        }
        
        changes = extract_changes(no_op_change)
        self.assertIsNone(changes)

    @patch("sys.argv", ["parse.py", "/fake/dir", "--state", "/fake/state.tfstate"])
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.exists")
    @patch("tfsec.parse.run_terraform_plan")
    def test_main_with_state_file(self, mock_run, mock_exists, mock_is_dir):
        from tfsec.parse import main
        
        # Mock path checks
        mock_is_dir.return_value = True
        mock_exists.return_value = True
        
        # Mock successful plan
        mock_run.return_value = MagicMock(
            error=None,
            json_plan={
                "resource_changes": [{
                    "address": "test_resource",
                    "type": "test_type",
                    "name": "test",
                    "change": self.sample_resource_change
                }]
            }
        )

        # Redirect stdout to capture output
        with patch("sys.stdout") as mock_stdout:
            main()
            
        # Verify run_terraform_plan was called with state file
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(len(args), 2)
        self.assertIsInstance(args[1], Path)

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

    def test_create_resource_changes_dict(self):
        sample_plan = {
            "resource_changes": [{
                "address": "test_resource",
                "type": "test_type",
                "name": "test",
                "change": self.sample_resource_change
            }]
        }
        
        changes = create_resource_changes_dict(sample_plan)
        
        self.assertIn("test_resource", changes)
        self.assertEqual(changes["test_resource"]["type"], "test_type")
        self.assertEqual(changes["test_resource"]["name"], "test")
        self.assertEqual(
            changes["test_resource"]["changes"]["source_ranges"]["before"],
            ["10.0.0.0/8"]
        )
        self.assertEqual(
            changes["test_resource"]["changes"]["source_ranges"]["after"],
            ["0.0.0.0/0"]
        )


if __name__ == "__main__":
    unittest.main()
