---
name: contributing
description: How to branch, commit, open a pull request, and drive CI to green in this repo. Use whenever you are about to commit, push, create a PR, or check CI status.
---

# Contributing workflow

## Branch

- Branch off the freshest upstream main, never a stale local main:
  `git fetch origin && git switch -c <type>/<slug> origin/main`.
- The working tree often holds the maintainer's local race data (dirty `data/`,
  `fpg_info.txt`). Keep those out of your commits: stage only files you changed
  (`git add <path> ...`), never `git add -A`.

## Commit

- Exactly ONE LINE, Conventional Commits: `git commit -m "type(scope): summary"`.
- No body, no `Co-Authored-By` trailer, ever. `cz check` validates
  `origin/main..HEAD` in CI, so a non-conventional subject fails the build.

## Before pushing

- `uv run pre-commit run --all-files` and `uv run pytest` must both pass.
- Everything tracked must be ASCII (the `no-non-ascii` hook covers markdown too).

## Pull request

- `git push -u origin <branch>` then
  `gh pr create --base main --title "..." --body "..."`.
- PR body is real content only: NO "Generated with Claude Code" line and no
  attribution/co-author footer. If a template appends one, remove it.
- Once CI is green, the README asks contributors to request review from @dchernykh1984.

## Watch CI to green

- Poll the authoritative rollup, not `gh pr checks` (its per-check status lags and can
  show `pending` for a while after a job has actually finished):

  ```
  gh pr view <n> --json statusCheckRollup \
    --jq '[.statusCheckRollup[] | {name:(.name//.context), s:(.conclusion//.state)}]'
  ```

- Checks that must all be SUCCESS: `pre-commit`, `commitizen`, `tests`, `audit`, and
  `build` (a `targets` job plus at least one platform build). `commitizen` only runs on
  non-main refs.
