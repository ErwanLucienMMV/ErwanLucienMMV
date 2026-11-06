# Profile language statistics

The profile ends with a local, self-contained [`assets/languages.svg`](../assets/languages.svg).
The original README is preserved; generation never reads or writes it.
Python 3.12 or newer and the standard library are sufficient.

## What the chart measures

For each selected public repository, the generator checks repository metadata
and requests [`GET /repos/{owner}/{repo}/languages`](https://docs.github.com/en/rest/repos/repos#list-repository-languages).
GitHub returns code bytes per language, as classified by
[GitHub Linguist](https://github.com/github-linguist/linguist).
Bytes are added across repositories and divided by the total byte count.
Large repositories therefore carry more weight than small ones.

This is an approximate distribution of repository code. It does not measure
skill, time spent, commits, or personal contributions in collaborative projects.
Generated, vendored and duplicated code can affect the result. Linguist overrides
can be added to `.gitattributes` in the source repositories through separate changes.
This feature does not modify any source repository.

## Repository selection

[`config/languages.json`](../config/languages.json) is the source of truth.
The initial selection was verified through the public GitHub API on 6 November
2026. It includes these 12 projects:

| Area | Selected repositories |
| --- | --- |
| Systems | `ft_irc`, `Inception`, `MyGNL`, `my_philosopher`, `my_pipex`, `mypushswap` |
| Web and personal projects | `AngularPortfolio`, `AtlasDominion`, `ft_transcendance`, `vrising-server-configurator-tool` |
| Training and tooling | `HNFormationAPI`, `TonTonTonBeaufSurDiscord` |

This is a configurable representative selection, not every repository on the
account. Adding a new public project requires adding its exact name to `include`.
Repository names are checked case-insensitively for exclusions and duplicates.

- `username`: the public GitHub account owning the selected projects.
- `include`: explicit repository names; no automatic discovery is performed.
- `exclude`: takes precedence over inclusion. `AngularPortfolioLive` is omitted
  as a deployment copy, and `ft_minishell` and `minirt` are excluded forks.
- The profile repository itself is always excluded, including its generated SVG.
- Forks and archived repositories are skipped unless named in `allow_forks` or
  `allow_archived`. Private repositories always stop publication before their
  language data is queried. Private statistics would require a separately
  approved authentication and disclosure strategy.
- `top_n`: show 1–12 leading languages, sorted by bytes descending then name.
- `show_other`: default `true`, combining the remaining languages into `Other`.
  If `false`, the chart explicitly says that percentages refer to displayed
  languages only and renormalizes that subset to 100%.

Displayed values use tenths of a percent. The generator floors each exact
fraction to tenths, then distributes the remaining tenths by largest fractional
remainder, resolving ties by the stable display order. Values always total
100.0%. Segment widths use the underlying byte counts. Known languages use fixed
colors; other colors derive from SHA-256, independent of Python hash randomization.

## Local use

```sh
python -m unittest discover -s tests -v
python scripts/generate_languages.py
```

Run the generator from any directory. Optional arguments are `--config PATH` and
`--output PATH.svg`. The default output is `assets/languages.svg`. An optional
`GITHUB_TOKEN` environment variable authenticates public API requests; a personal
access token is unnecessary. Never put credentials into the configuration.

Each selected project needs two REST requests, so the initial configuration needs
24 per generation. Unauthenticated local use can hit GitHub's API limits.
Requests have a 20-second timeout and at most three attempts for transport
errors, HTTP 429 and transient server failures. HTTP 401/403/404 and malformed
responses fail with a diagnostic. Response bodies and tokens are not logged.

Collection finishes and the generated XML is validated before an atomic file
replacement. Any failure preserves the previous SVG. If a successful collection
contains no code, the output is a valid SVG saying “No language data available”.
Identical data does not change the file or its modification time. The SVG has no
changing timestamp, JavaScript, remote image, font download or external service.
Its accessible description includes the values, and its colors adapt to the
viewer's light or dark color scheme.
