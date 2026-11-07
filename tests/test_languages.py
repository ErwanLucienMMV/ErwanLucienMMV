"""Offline regression tests for data correctness and safe API failures."""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from scripts.language_data import (
    GitHubClient, StatsError, collect_languages, distribution, language_color,
    load_config, validate_languages,
)
from scripts.generate_languages import generate, main, render_svg, write_if_changed
import xml.etree.ElementTree as ET


def config(**overrides):
    return dict(username="example", include=["one", "two"], exclude=[],
                allow_forks=[], allow_archived=[], top_n=7, show_other=True, **overrides)


def metadata(**overrides):
    return dict(private=False, fork=False, archived=False, **overrides)


class DataTests(unittest.TestCase):
    def test_aggregate_and_deterministic_ties(self):
        client = Mock()
        client.get.side_effect = [metadata(), {"C": 30, "Python": 10}, metadata(), {"Python": 20, "Zero": 0}]
        self.assertEqual(collect_languages(config(), client), {"C": 30, "Python": 30})
        self.assertEqual([row["name"] for row in distribution({"Python": 30, "C": 30})], ["C", "Python"])

    def test_profile_and_explicit_exclusions_are_never_requested(self):
        settings = config()
        settings.update(include=["EXAMPLE", "one", "two"], exclude=["ONE", "two"])
        client = Mock()
        self.assertEqual(collect_languages(settings, client), {})
        client.get.assert_not_called()

    def test_forks_and_archives_require_explicit_opt_in(self):
        for flag, option in (("fork", "allow_forks"), ("archived", "allow_archived")):
            with self.subTest(flag=flag):
                repo = metadata()
                repo[flag] = True
                client = Mock()
                client.get.return_value = repo
                settings = config()
                settings["include"] = ["one"]
                self.assertEqual(collect_languages(settings, client), {})
                self.assertEqual(client.get.call_count, 1)
                settings[option] = ["ONE"]
                client.get.side_effect = [repo, {"C": 10}]
                self.assertEqual(collect_languages(settings, client), {"C": 10})

    def test_private_data_is_never_queried(self):
        client = Mock()
        repo = metadata()
        repo["private"] = True
        client.get.return_value = repo
        with self.assertRaisesRegex(StatsError, "private"):
            collect_languages(config(), client)
        self.assertEqual(client.get.call_count, 1)

    def test_malformed_metadata_stops_collection(self):
        for value in ({}, [], {"private": False, "fork": 0, "archived": False}):
            with self.subTest(value=value), self.assertRaises(StatsError):
                collect_languages(config(), Mock(get=Mock(return_value=value)))

    def test_bad_language_data(self):
        for value in ([], None, {"C": -1}, {"C": True}, {"C": 1.5}, {"": 1}, {"bad\x00": 1}):
            with self.subTest(value=value), self.assertRaises(StatsError):
                validate_languages(value)

    def test_percentages_sum_to_one_hundred(self):
        rows = distribution({"A": 1, "B": 1, "C": 1})
        self.assertEqual([row["tenths"] for row in rows], [334, 333, 333])
        self.assertEqual(sum(row["tenths"] for row in rows), 1000)

    def test_other_preserves_original_denominator(self):
        rows = distribution({"C": 50, "Python": 30, "Shell": 15, "Makefile": 5}, top_n=2)
        self.assertEqual([(row["name"], row["tenths"]) for row in rows], [("C", 500), ("Python", 300), ("Other", 200)])

    def test_hide_other_renormalizes_displayed_subset(self):
        self.assertEqual(distribution({"C": 50, "Python": 30}, top_n=1, show_other=False)[0]["tenths"], 1000)

    def test_zero_empty_and_single_language(self):
        self.assertEqual(distribution({}), [])
        self.assertEqual(distribution({"C": 0}), [])
        self.assertEqual(distribution({"C": 123})[0]["tenths"], 1000)

    def test_unknown_language_color_is_stable(self):
        self.assertEqual(language_color("Unknown"), language_color("Unknown"))
        self.assertNotEqual(language_color("Unknown"), language_color("Other unknown"))

    def test_config_defaults_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"username": "example", "include": ["one"]}))
            self.assertEqual(load_config(path)["top_n"], 7)
            for changes in ({"top_n": True}, {"top_n": 0}, {"include": ["one", "ONE"]},
                            {"include": ["../bad"]}, {"show_other": 1}, {"username": "a/b"}):
                path.write_text(json.dumps({**config(), **changes}))
                with self.subTest(changes=changes), self.assertRaises(StatsError):
                    load_config(path)


class ClientTests(unittest.TestCase):
    @patch("scripts.language_data.urlopen")
    def test_request_headers_and_timeout(self, open_url):
        open_url.return_value.__enter__.return_value = io.BytesIO(b'{"C": 4}')
        self.assertEqual(GitHubClient("secret").get("/repos/example/one/languages"), {"C": 4})
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(open_url.call_args.kwargs["timeout"], 20)
        self.assertTrue(request.get_header("User-agent"))

    @patch("scripts.language_data.urlopen")
    def test_public_unauthenticated_request(self, open_url):
        open_url.return_value.__enter__.return_value = io.BytesIO(b'{}')
        GitHubClient("").get("/repos/example/one")
        self.assertFalse(open_url.call_args.args[0].has_header("Authorization"))

    @patch("scripts.language_data.time.sleep")
    @patch("scripts.language_data.urlopen")
    def test_http_failures_and_bounded_retries(self, open_url, sleep):
        for status in (401, 403, 404, 429, 500, 503):
            open_url.reset_mock()
            open_url.side_effect = HTTPError("https://api.github.com", status, "private body secret", {}, None)
            with self.subTest(status=status), self.assertRaises(StatsError) as raised:
                GitHubClient("secret").get("/repos/example/one")
            self.assertNotIn("secret", str(raised.exception))
            self.assertEqual(open_url.call_count, 3 if status in (429, 500, 503) else 1)

    @patch("scripts.language_data.time.sleep")
    @patch("scripts.language_data.urlopen")
    def test_network_failure_is_bounded(self, open_url, sleep):
        open_url.side_effect = URLError("connection failed")
        with self.assertRaises(StatsError):
            GitHubClient("").get("/repos/example/one")
        self.assertEqual(open_url.call_count, 3)

    @patch("scripts.language_data.urlopen")
    def test_invalid_json(self, open_url):
        open_url.return_value.__enter__.return_value = io.BytesIO(b'not json')
        with self.assertRaisesRegex(StatsError, "invalid JSON"):
            GitHubClient("").get("/repos/example/one")


class RenderingTests(unittest.TestCase):
    def test_svg_is_valid_accessible_and_self_contained(self):
        svg = render_svg({"C": 55, "Python": 45})
        root = ET.fromstring(svg)
        ns = {"s": "http://www.w3.org/2000/svg"}
        self.assertEqual(root.attrib["role"], "img")
        self.assertTrue(root.find("s:title", ns).text)
        self.assertIn("55.0%", root.find("s:desc", ns).text)
        self.assertIn(b"prefers-color-scheme: dark", svg)
        self.assertNotIn(b"<script", svg)
        self.assertNotIn(b"<image", svg)

    def test_untrusted_text_is_escaped(self):
        name = '<script>"hello" & world</script>'
        svg = render_svg({name: 10})
        root = ET.fromstring(svg)
        self.assertIn(name, root.find("{http://www.w3.org/2000/svg}desc").text)
        self.assertNotIn(b"<script>", svg)

    def test_empty_single_and_many_languages(self):
        self.assertIn(b"No language data available", render_svg({}))
        self.assertIn(b"100.0%", render_svg({"C": 1}))
        data = {f"Language {i}": i + 1 for i in range(50)}
        svg = render_svg(data, top_n=12)
        root = ET.fromstring(svg)
        labels = root.findall("{http://www.w3.org/2000/svg}circle")
        self.assertEqual(len(labels), 13)
        self.assertIn(b"Other", svg)

    def test_very_long_names_have_bounded_labels(self):
        svg = render_svg({"W" * 128: 20})
        self.assertIn(b'textLength="530"', svg)
        self.assertIn(("W" * 47 + "…").encode(), svg)

    def test_reproducible_regardless_of_input_order(self):
        data = {"C": 30, "Python": 20, "Unknown": 5}
        self.assertEqual(render_svg(data), render_svg(dict(reversed(list(data.items())))))

    def test_identical_output_does_not_change_file_or_mtime(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "languages.svg"
            svg = render_svg({"C": 1})
            self.assertTrue(write_if_changed(path, svg))
            modified = path.stat().st_mtime_ns
            self.assertFalse(write_if_changed(path, svg))
            self.assertEqual(path.stat().st_mtime_ns, modified)
            self.assertEqual(path.read_bytes(), svg)

    def test_generation_failure_preserves_existing_svg(self):
        for failure in (StatsError("HTTP 403 rate limit"), StatsError("HTTP 404"),
                        StatsError("malformed data"), StatsError("network failed")):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "languages.svg"
                path.write_bytes(b"previous valid statistics")
                settings = Path(folder) / "config.json"
                settings.write_text(json.dumps(config()))
                client = Mock()
                client.get.side_effect = failure
                with self.assertRaises(StatsError):
                    generate(settings, path, client)
                self.assertEqual(path.read_bytes(), b"previous valid statistics")

    @patch("scripts.generate_languages.os.replace", side_effect=OSError("disk failure"))
    def test_atomic_write_failure_preserves_existing_svg(self, replace):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "languages.svg"
            path.write_bytes(b"previous statistics")
            with self.assertRaises(OSError):
                write_if_changed(path, render_svg({"C": 10}))
            self.assertEqual(path.read_bytes(), b"previous statistics")
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_two_complete_fixture_runs_have_no_diff(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "languages.svg"
            settings = Path(folder) / "config.json"
            settings.write_text(json.dumps(config()))
            client = Mock()
            for expected_change in (True, False):
                client.get.side_effect = [metadata(), {"C": 30}, metadata(), {"Python": 20}]
                self.assertEqual(generate(settings, path, client), expected_change)

    def test_cli_refuses_readme_as_output(self):
        with patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--output", "README.md"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
