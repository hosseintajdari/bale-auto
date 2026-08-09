import copy
import unittest

from scripts.validate_policy import validate_policy


def valid_policy():
    return {
        "version": 1,
        "default": "deny",
        "intents": {
            "system.health.read": {
                "risk": "low",
                "approval": "not_required",
                "executor": "health_check",
                "timeout_seconds": 10,
                "read_only": True,
            }
        },
    }


class PolicyValidationTests(unittest.TestCase):
    def setUp(self):
        self.policy = copy.deepcopy(valid_policy())

    def test_accepts_the_single_read_only_health_intent(self):
        self.assertEqual(validate_policy(self.policy), [])

    def test_rejects_a_policy_without_default_deny(self):
        self.policy["default"] = "allow"
        self.assertIn("default must be deny", validate_policy(self.policy))

    def test_rejects_unsupported_top_level_fields(self):
        self.policy["commands"] = []
        self.assertIn("unsupported top-level field: commands", validate_policy(self.policy))

    def test_rejects_an_unknown_intent(self):
        self.policy["intents"]["system.shell.run"] = self.policy["intents"].pop(
            "system.health.read"
        )
        self.assertIn("unsupported intent: system.shell.run", validate_policy(self.policy))

    def test_rejects_shell_or_command_fields(self):
        self.policy["intents"]["system.health.read"]["command"] = "uname -a"
        self.assertIn("unsupported field: command", validate_policy(self.policy))

    def test_rejects_a_non_read_only_intent(self):
        self.policy["intents"]["system.health.read"]["read_only"] = False
        self.assertIn("read_only must be true", validate_policy(self.policy))

    def test_rejects_an_unbounded_timeout(self):
        self.policy["intents"]["system.health.read"]["timeout_seconds"] = 60
        self.assertIn(
            "timeout_seconds must be an integer from 1 through 30",
            validate_policy(self.policy),
        )

    def test_rejects_a_different_executor(self):
        self.policy["intents"]["system.health.read"]["executor"] = "shell"
        self.assertIn("executor must be health_check", validate_policy(self.policy))

    def test_invalid_input_returns_errors_instead_of_raising(self):
        self.assertEqual(validate_policy([]), ["policy must be an object"])


if __name__ == "__main__":
    unittest.main()
