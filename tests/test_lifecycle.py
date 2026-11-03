"""Verify image selection and recovery without touching a running deployment."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bridge


class ImageLifecycleTests(unittest.TestCase):
    def test_update_and_rollback_use_the_running_image(self):
        self.exercise_update(fail=False)

    def test_failed_update_restores_running_image(self):
        self.exercise_update(fail=True)

    def exercise_update(self, *, fail):
        previous = "ghcr.io/openai/tunnel-client:v0.0.18@sha256:" + "a" * 64
        candidate = bridge.PIN
        active = previous
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            local = root / ".local"
            (root / ".env").write_text("BRIDGE_UID=1000\n")

            def inspect(args, **kwargs):
                return subprocess.CompletedProcess(args, 0, stdout=active + "\n")

            def start(image):
                nonlocal active
                active = image
                if fail and image == candidate:
                    raise subprocess.CalledProcessError(1, "fixture startup")

            with (patch.multiple(bridge, ROOT=root, LOCAL=local),
                  patch.object(bridge, "containers", return_value=["fixture"]),
                  patch.object(bridge, "check_checkout"),
                  patch.object(bridge, "validate"),
                  patch.object(bridge, "run", side_effect=inspect),
                  patch.object(bridge, "compose", return_value=subprocess.CompletedProcess(
                      [], 0, stdout="fixture\n")),
                  patch.object(bridge, "start", side_effect=start),
                  patch.object(sys, "argv", ["bridge.py", "update"])):
                if fail:
                    with self.assertRaises(subprocess.CalledProcessError):
                        bridge.main()
                    self.assertEqual(active, previous)
                    self.assertFalse((local / "rollback.json").exists())
                else:
                    bridge.main()
                    self.assertEqual(active, candidate)
                    saved = json.loads((local / "rollback.json").read_text())
                    self.assertEqual(saved["image"], previous)
                    with patch.object(sys, "argv", ["bridge.py", "rollback"]):
                        bridge.main()
                    self.assertEqual(active, previous)
                self.assertIn("BRIDGE_IMAGE=" + previous, (root / ".env").read_text())
