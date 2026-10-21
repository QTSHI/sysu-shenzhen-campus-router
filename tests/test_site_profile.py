import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("site_profile_tool", ROOT / "tools" / "site_profile.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class SiteProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = TOOL.load_profile(TOOL.DEFAULT_PROFILE)

    def reject(self, profile):
        with self.assertRaises(TOOL.ProfileError):
            TOOL.validate_profile(profile)

    def test_interrupted_case_and_anonymous_summary(self):
        value = TOOL.summary(self.profile)
        self.assertEqual(value["scope"], "one_wall_port")
        self.assertEqual(value["observation"]["result"], "interrupted")
        self.assertEqual(value["observation"]["successful_probe_pair_count"], 396)
        self.assertEqual(value["observation"]["service_online_sample_count"], 80)
        self.assertFalse(value["observation"]["recording_active"])
        self.assertFalse(value["observation"]["twenty_four_hours_passed"])
        self.assertFalse(value["network_verified_by_this_tool"])
        self.assertIn("6小时35分16秒", TOOL.chinese_report(value))
        self.assertIn("不访问网络", TOOL.chinese_report(value))
        self.assertFalse(value["account_limit_proven"])

    def test_fake_24h_pass_rejected_even_with_enough_time(self):
        observation = self.profile["observation"]
        observation["twenty_four_hours_passed"] = True
        self.reject(self.profile)
        observation["recorded_seconds"] = 86400
        self.reject(self.profile)
        observation.update(result="completed", reason="duration_elapsed")
        self.reject(self.profile)  # 396 minute-spaced samples cannot cover 24 hours.
        observation.update(sample_count=1441, private_sample_count=1441, probe_cycle_count=1441,
                           successful_probe_pair_count=1441, service_sample_count=289,
                           service_online_sample_count=289)
        self.assertIs(TOOL.validate_profile(self.profile), self.profile)
        self.assertTrue(TOOL.summary(self.profile)["consistency_only"])
        self.assertFalse(TOOL.summary(self.profile)["network_verified_by_this_tool"])
        for key, value in (("recorded_seconds", 86399), ("successful_probe_pair_count", 1440),
                           ("service_online_sample_count", 288), ("gap_count", 1),
                           ("sample_count", 1442), ("maximum_interval_seconds", 0),
                           ("maximum_interval_seconds", 90.001)):
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.profile)
                candidate["observation"][key] = value
                self.reject(candidate)

    def test_inverted_counts_and_boolean_numbers_rejected(self):
        for key, value in (("private_sample_count", 397), ("probe_cycle_count", 397),
                           ("successful_probe_pair_count", 397), ("service_sample_count", 397),
                           ("service_online_sample_count", 81), ("gap_count", 397), ("sample_count", True)):
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.profile)
                candidate["observation"][key] = value
                self.reject(candidate)

    def test_active_result_and_reason_must_agree(self):
        self.profile["observation"]["recording_active"] = True
        self.reject(self.profile)
        self.profile["observation"].update(result="running", reason="in_progress")
        TOOL.validate_profile(self.profile)
        self.profile["observation"]["result"] = "unknown"
        self.reject(self.profile)
        self.profile["observation"].update(result="interrupted", recording_active=False)
        self.reject(self.profile)

    def test_duplicate_fields_rejected_at_every_depth(self):
        raw = json.dumps(self.profile)
        for mutated in (raw[:-1] + ',"schema_version":1}',
                        raw.replace('"sample_count": 396', '"sample_count":396,"sample_count":396')):
            with self.subTest(mutated=mutated[:25]):
                with self.assertRaises(TOOL.ProfileError):
                    TOOL.parse_profile(mutated.encode("utf-8"))

    def test_negative_nonfinite_boolean_and_nan_rates_rejected(self):
        for value in (-1, float("nan"), float("inf"), True):
            with self.subTest(value=value):
                candidate = copy.deepcopy(self.profile)
                candidate["measurements"][0]["single_download"]["mbps"] = value
                self.reject(candidate)
        raw = json.dumps(self.profile).replace('"mbps": 123.077', '"mbps": NaN')
        with self.assertRaises(TOOL.ProfileError):
            TOOL.parse_profile(raw.encode("utf-8"))

    def test_unknown_fields_versions_claims_and_wrong_units_rejected(self):
        for mutate in (
            lambda item: item.update(schema_version=2),
            lambda item: item.update(password="PRIVATE_SENTINEL"),
            lambda item: item["claims"].update(account_limit_proven=True),
            lambda item: item["claims"].update(multiple_accounts_tested=True),
            lambda item: item["measurements"][0]["single_download"].update(connections=4),
        ):
            candidate = copy.deepcopy(self.profile)
            mutate(candidate)
            self.reject(candidate)

    def test_cli_is_read_only_and_redacts_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            original = json.dumps(self.profile, ensure_ascii=False).encode("utf-8")
            path.write_bytes(original)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(TOOL.main(["--profile", str(path), "--json"]), 0)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(json.loads(output.getvalue())["observation"]["result"], "interrupted")
            self.profile["password"] = "PRIVATE_SENTINEL"
            path.write_text(json.dumps(self.profile), encoding="utf-8")
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                self.assertEqual(TOOL.main(["--profile", str(path)]), 2)
            self.assertNotIn("PRIVATE_SENTINEL", output.getvalue() + errors.getvalue())
            self.assertNotIn(str(path), output.getvalue() + errors.getvalue())


if __name__ == "__main__":
    unittest.main()
