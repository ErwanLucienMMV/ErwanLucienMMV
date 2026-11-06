"""Fetch public GitHub language bytes and apportion deterministic percentages.

Only explicitly configured repositories are queried; no repository discovery or
pagination is necessary during generation. Uses Python's standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class StatsError(ValueError):
    """An expected configuration, API, or data error safe to show publicly."""


def load_config(path: Path) -> dict:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise StatsError("Cannot read valid language configuration") from error
    if not isinstance(config, dict):
        raise StatsError("Configuration must be an object")
    username = config.get("username")
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", username):
        raise StatsError("Invalid GitHub username")
    for key in ("include", "exclude", "allow_forks", "allow_archived"):
        names = config.get(key, [])
        if not isinstance(names, list) or any(
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name)
            or name in (".", "..")
            for name in names
        ):
            raise StatsError(f"{key} must be a list of repository names")
        if len({name.casefold() for name in names}) != len(names):
            raise StatsError(f"Duplicate repository in {key}")
        config[key] = names
    top_n = config.get("top_n", 7)
    if type(top_n) is not int or not 1 <= top_n <= 12:
        raise StatsError("top_n must be an integer between 1 and 12")
    config["top_n"] = top_n
    if type(config.get("show_other", True)) is not bool:
        raise StatsError("show_other must be a boolean")
    config.setdefault("show_other", True)
    return config


class GitHubClient:
    """Bounded requests and retries; never print credentials or response bodies."""

    def __init__(self, token: str | None = None):
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN")

    def get(self, path: str):
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-language-statistics",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(3):
            try:
                request = Request(f"https://api.github.com{path}", headers=headers)
                with urlopen(request, timeout=20) as response:
                    return json.load(response)
            except HTTPError as error:
                retryable = error.code in (429, 500, 502, 503, 504)
                if retryable and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                detail = {
                    401: "authentication failed",
                    403: "access denied or API rate limit reached",
                    404: "repository missing or inaccessible",
                    429: "API rate limit reached",
                }.get(error.code, "GitHub request failed")
                raise StatsError(f"{path}: HTTP {error.code}; {detail}") from error
            except (URLError, TimeoutError, OSError) as error:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise StatsError(f"{path}: network request failed after 3 attempts") from error
            except (ValueError, UnicodeError) as error:
                raise StatsError(f"{path}: invalid JSON response") from error


def validate_languages(data: object) -> dict[str, int]:
    if not isinstance(data, dict):
        raise StatsError("Language response must be an object")
    for language, size in data.items():
        if (
            not isinstance(language, str)
            or not language.strip()
            or len(language) > 128
            or any(not (c in "\t\n\r" or "\x20" <= c <= "\ud7ff" or "\ue000" <= c <= "\ufffd" or "\U00010000" <= c <= "\U0010ffff") for c in language)
            or type(size) is not int
            or size < 0
        ):
            raise StatsError("Invalid language name or byte count")
    return data


def collect_languages(config: dict, client: GitHubClient) -> dict[str, int]:
    excluded = {name.casefold() for name in config["exclude"]}
    excluded.add(config["username"].casefold())
    allowed_forks = {name.casefold() for name in config["allow_forks"]}
    allowed_archived = {name.casefold() for name in config["allow_archived"]}
    totals: dict[str, int] = {}
    for name in sorted(config["include"], key=str.casefold):
        if name.casefold() in excluded:
            continue
        path = f"/repos/{config['username']}/{name}"
        repo = client.get(path)
        if not isinstance(repo, dict) or any(
            type(repo.get(field)) is not bool for field in ("private", "fork", "archived")
        ):
            raise StatsError(f"{path}: invalid repository metadata")
        if repo["private"]:
            raise StatsError("A selected repository is private; publication stopped")
        if repo["fork"] and name.casefold() not in allowed_forks:
            continue
        if repo["archived"] and name.casefold() not in allowed_archived:
            continue
        try:
            languages = validate_languages(client.get(f"{path}/languages"))
        except StatsError as error:
            raise StatsError(f"{path}: language collection failed; {error}") from error
        for language, size in languages.items():
            if size:
                totals[language] = totals.get(language, 0) + size
    return dict(sorted(totals.items(), key=lambda item: (-item[1], item[0])))


COLORS = {
    "C": "#555555", "C++": "#f34b7d", "C#": "#178600",
    "CSS": "#663399", "Dockerfile": "#384d54", "HTML": "#e34c26",
    "Java": "#b07219", "JavaScript": "#f1e05a", "Makefile": "#427819",
    "Python": "#3572a5", "Rust": "#dea584", "Shell": "#89e051",
    "TypeScript": "#3178c6", "Other": "#8b949e",
}


def language_color(language: str) -> str:
    if language in COLORS:
        return COLORS[language]
    hue = int(hashlib.sha256(language.encode("utf-8")).hexdigest()[:8], 16) % 360
    return f"hsl({hue}, 55%, 50%)"


def distribution(totals: dict[str, int], top_n: int = 7, show_other: bool = True) -> list[dict]:
    """Largest remainders allocate 1,000 tenths of a percent exactly.

    With show_other=False, percentages refer to the displayed languages only.
    Ties are resolved by descending bytes and then language name.
    """
    validate_languages(totals)
    ordered = sorted(((name, size) for name, size in totals.items() if size), key=lambda item: (-item[1], item[0]))
    visible = ordered[:top_n]
    remainder = sum(size for _, size in ordered[top_n:])
    if show_other and remainder:
        # A real language named Other shares its row with the grouped tail.
        for index, (name, size) in enumerate(visible):
            if name == "Other":
                visible[index] = (name, size + remainder)
                break
        else:
            visible.append(("Other", remainder))
    total = sum(size for _, size in visible)
    if not total:
        return []
    tenths = [size * 1000 // total for _, size in visible]
    priority = sorted(range(len(visible)), key=lambda i: (-(visible[i][1] * 1000 % total), i))
    for index in priority[:1000 - sum(tenths)]:
        tenths[index] += 1
    return [
        {"name": name, "bytes": size, "tenths": tenths[i], "color": language_color(name)}
        for i, (name, size) in enumerate(visible)
    ]
