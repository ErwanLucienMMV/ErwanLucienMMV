#!/usr/bin/env bash
# Run only in a clean workflow checkout of the default-branch triggering commit.
set -euo pipefail

: "${DEFAULT_BRANCH:?DEFAULT_BRANCH must name the repository default branch}"

# Refuse an unexpected index rather than accidentally committing other files.
if [[ -n "$(git diff --cached --name-only)" ]]; then
  echo '::error::Unexpected staged files; refusing to publish.'
  exit 1
fi

git add -- assets/languages.svg
if git diff --cached --quiet -- assets/languages.svg; then
  echo 'Language statistics unchanged; nothing to publish.'
  exit 0
fi

git -c user.name='github-actions[bot]' \
    -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
    commit -m 'chore: update profile language statistics' -- assets/languages.svg

# A regular push fails safely if the default branch advanced or is protected.
# Do not force, rebase, or change any protection to work around a rejection.
if ! git push origin "HEAD:refs/heads/$DEFAULT_BRANCH"; then
  echo '::error::SVG push rejected. Review branch changes or prepare an approved update PR; protections were left intact.'
  exit 1
fi
