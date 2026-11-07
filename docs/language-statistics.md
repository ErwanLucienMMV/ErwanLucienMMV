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
The current selection was verified through the public GitHub API on 7 November
2026. It includes these 21 projects:

| Area | Selected repositories |
| --- | --- |
| Systems | `ft_irc`, `Inception`, `MyGNL`, `my_philosopher`, `my_pipex`, `mypushswap`, `minirt`, `ft_minishell`, `DrQuinn`, `my_so_long` |
| C++ exercises | `Cpp00`, `Cpp03`, `Cpp04`, `Cpp08`, `Cpp09` |
| Web and personal projects | `AngularPortfolio`, `AtlasDominion`, `ft_transcendance`, `vrising-server-configurator-tool` |
| Training and tooling | `HNFormationAPI`, `TonTonTonBeaufSurDiscord` |

This is a configurable representative selection, not every repository on the
account. Adding a new public project requires adding its exact name to `include`.
Repository names are checked case-insensitively for exclusions and duplicates.

- `username`: the public GitHub account owning the selected projects.
- `include`: explicit repository names; no automatic discovery is performed.
- `exclude`: takes precedence over inclusion. `AngularPortfolioLive` is omitted
  as a deployment copy. `minirt` and `ft_minishell` are included and explicitly
  listed in `allow_forks` because they are collaborative projects I contributed to.
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

Each selected project needs two REST requests, so the current configuration needs
42 per generation. Unauthenticated local use can hit GitHub's API limits.
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

## GitHub Actions

[`update-languages.yml`](../.github/workflows/update-languages.yml) has manual
`workflow_dispatch` and scheduled `17 */6 * * *` triggers: 00:17, 06:17, 12:17
and 18:17 UTC. GitHub may delay scheduled runs and can disable schedules in a
public repository after 60 days without repository activity; check the Actions
tab if updates stop. See GitHub's
[event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

The validation job has `contents: read` and runs all offline tests. Only the
publishing job has `contents: write`, and its condition restricts it to the
default branch. A manual run on another branch can test the code but skips
publication. Actions are pinned to verified commit SHAs. The generator uses the
built-in `GITHUB_TOKEN`; no personal token, cross-repository secret or external
hosting is required. See
[GitHub's token documentation](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).

The publisher stages only `assets/languages.svg`, refuses unexpected staged
files, and skips the commit and push if its bytes are unchanged. It never writes
the README. A single concurrency group serializes publishing runs. The regular
push fails if a newer commit arrived or branch protection rejects the bot. The
workflow does not force a push, rewrite history or alter protections. Review and
rerun a stale update; if protection requires a PR, prepare an SVG-only update PR
through the team's approved process. Automatic PR creation is not configured in
V1 and would require an explicit decision and the additional PR permission.

[`test-languages.yml`](../.github/workflows/test-languages.yml) runs on relevant
branch pushes and pull requests, plus manual invocation once registered on the
default branch. It has read-only repository permissions, runs the same tests,
and generates a live SVG in the runner's temporary directory. That public-only
preview is available as a seven-day workflow artifact. It never publishes a
commit. SVG-only bot updates do not match its push path filter, and updates
made with `GITHUB_TOKEN` normally do not trigger further workflows.

The initial publishing workflow cannot be manually dispatched before it exists
on the default branch. Feature-branch CI validates this implementation without
publishing to `main`. After review and merge, run **Update language statistics**
once on the default branch and verify that an unchanged SVG produces no commit;
then check a scheduled run. This post-merge production check remains a deployment
step and is not claimed by local or feature-branch validation.

For a future V2, source repositories could request an update with
`repository_dispatch` or `workflow_dispatch` after a merge. That requires an
explicitly approved GitHub App or other credential with the appropriate
cross-repository permissions. No such credential or source workflow is installed
by V1.
