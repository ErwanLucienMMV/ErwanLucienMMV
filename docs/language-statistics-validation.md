# Language statistics validation

Baseline: `08afd57fb5933fbea94639ab881f56a178c4fbdb` on `main`.
Implementation branch: `feat/profile-language-statistics`.
Validation date: 6 November 2026.

## Existing repository preserved

The initial checkout was clean and contained only `README.md`. No existing
workflow, script or test was replaced. The public profile repository's default
branch was confirmed as `main`; public branch metadata reported no active
protection or rules. No repository setting was changed.

The original working README had 11,931 bytes (CRLF line endings), with SHA-256:

```text
e324c32a047a43284fa04efb6e9b07099be9752160d2266b13b51fd514314ce1
```

The updated working README starts with those exact original bytes. Its
Git-normalized content also starts with the exact baseline Git blob. The only
README change is this append:

```diff
@@ -370,0 +371,11 @@
+
+
+<!-- LANGUAGE_STATS:START -->
+
+## Languages across my projects
+
+![Language distribution](./assets/languages.svg)
+
+Based on code bytes in selected public repositories. [Method, scope and limitations](./docs/language-statistics.md).
+
+<!-- LANGUAGE_STATS:END -->
```

Both markers occur exactly once. No commit was amended, rebased, squashed or
force-pushed, and no change was pushed directly to `main`.

## Data and rendering

Two consecutive live generations queried GitHub's public API for the 12
configured projects. The first wrote the SVG; the second reported
`Language SVG unchanged` and produced the same SHA-256:

```text
d3634824fdbbe374e52382ae6e2ab3f354d70b3e0ef1317a5a028579e62baabb
```

| Language | Displayed share |
| --- | ---: |
| TypeScript | 62.0% |
| JavaScript | 16.6% |
| C | 7.3% |
| C++ | 5.4% |
| HTML | 4.6% |
| CSS | 1.4% |
| Python | 0.9% |
| Other | 1.8% |
| **Total** | **100.0%** |

The 720 × 446 SVG was parsed as XML and rasterized for visual inspection in both
light and dark themes. The local renderer does not expose a preferred color
scheme; the dark preview activated the exact dark CSS rules for that check.
Empty-data, single-language, long-label and many-language fixtures were also
rendered. Legends and percentages fit the card. The full accessible description
retains language names that are shortened visually.

## Tests and workflow checks

`python -m unittest discover -s tests -v` passes **31 tests**:

- Multi-project aggregation, selection exclusions, explicit fork/archive opt-ins,
  private-repository refusal and malformed metadata.
- Integer byte validation, empty/zero data, one language, deterministic order,
  grouping, unknown language colors and displayed totals of exactly 100.0%.
- Request authentication and timeouts, HTTP 401/403/404, bounded rate-limit and
  transient retries, transport failures and malformed JSON.
- Accessible, self-contained XML, escaping of untrusted text, bounded labels and
  byte-identical fixture rendering.
- Two complete unchanged fixture runs preserve file contents and modification
  time; API and atomic-write failures preserve the previous SVG.
- Actual publisher runs against temporary local Git remotes: no-op output makes
  no commit, changed output commits only the SVG, unexpected staged files stop
  publication, and a concurrent remote commit rejects the push without being
  overwritten.

Both workflow files pass YAML parsing with duplicate-key detection and
`actionlint` 1.7.12. `git diff --check` passes. Temporary renderer and lint tools
were installed outside the repository; production has no third-party Python
dependencies.

The scheduled/manual default-branch publisher requires a post-merge smoke test.
Feature-branch validation does not publish to `main`, and this branch is left
for review without merging.
