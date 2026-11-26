"""Autoconfiguration must work outside the default installation directory."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import emonhub_auto_conf as autoconf


class AutoConfTest(unittest.TestCase):
    def test_loads_bundled_templates_from_unrelated_working_directory(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                result = autoconf.EmonHubAutoConf({"hub": {"autoconf": "1"}})
            finally:
                os.chdir(previous)
        self.assertTrue(result.enabled)
        self.assertEqual(result.available["emonpi"]["nodeids"], [5])
        self.assertEqual(result.available["emonpi"]["datalength"], 24)
        self.assertEqual(result.available["emonpi"]["rx"]["scales"][3], 0.01)

    def test_disabled_autoconf_does_not_load_templates(self):
        for hub in ({}, {"autoconf": "0"}):
            with self.subTest(hub=hub):
                with mock.patch.object(autoconf, "ConfigObj") as loader:
                    result = autoconf.EmonHubAutoConf({"hub": hub})
                loader.assert_not_called()
                self.assertFalse(result.enabled)
                self.assertEqual(result.available, {})

    def test_enabled_autoconf_reports_missing_templates(self):
        with mock.patch.object(autoconf, "ConfigObj", side_effect=OSError("missing templates")):
            with self.assertRaisesRegex(autoconf.EmonHubAutoConfError, "missing templates"):
                autoconf.EmonHubAutoConf({"hub": {"autoconf": "1"}})


if __name__ == "__main__":
    unittest.main()
