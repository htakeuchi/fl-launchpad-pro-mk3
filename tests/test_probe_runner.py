import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
RUNNER = REPO_DIR / "scripts" / "request-fl-capability-probe.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("probe_runner_under_test", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProbeRunnerTests(unittest.TestCase):
    def test_find_result_and_retire_request_file(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            script_dir = Path(tmp)
            request_id, request_path = runner.write_probe_request(script_dir)
            result_path = script_dir / runner.RESULT_FILE
            result_path.write_text(
                json.dumps({"request": {"request_id": request_id}, "probe": "launchpad_capability_probe"}) + "\n",
                encoding="utf-8",
            )

            result = runner.find_result(result_path, request_id)
            runner.retire_request_file(request_path, request_id)

            self.assertEqual(result["probe"], "launchpad_capability_probe")
            self.assertFalse(request_path.exists())
            self.assertTrue((script_dir / f"{runner.REQUEST_FILE}.last-run-{request_id}").exists())


if __name__ == "__main__":
    unittest.main()
