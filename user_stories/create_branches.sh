#!/usr/bin/env bash
# Creates Varnika's 9 story branches (stacked, in this order) in YOUR clone of the team repo.
#
# Usage (Git Bash on Windows, or any terminal), from INSIDE your clone:
#     bash /path/to/create_branches.sh            # creates the branches locally
#     bash /path/to/create_branches.sh --push     # ...and pushes each one to GitHub (remote "origin")
#
# It only ADDS files (training/, member2_dev/, loadtest/, docs/member2/). It does not touch
# anyone else's files. The commits keep Varnika as the author.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCHES="$HERE/patches"
PUSH=false; [ "${1:-}" = "--push" ] && PUSH=true

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Run this inside your clone of the repo."; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "You have uncommitted changes. Commit or stash them first."; exit 1; }

BASE="${BASE_BRANCH:-main}"
git checkout -q "$BASE"
if git remote get-url origin >/dev/null 2>&1; then git pull -q --ff-only origin "$BASE" || true; fi

# branch name : last patch number belonging to it  (patches are applied in order, each branch builds on the previous)
PLAN=(
  "feature/us-06-model-catalogue:1"
  "feature/us-07-hyperparameters:2"
  "feature/us-08-background-training:3"
  "feature/us-11-unit-tests:4"
  "feature/us-20-training-speed:6"
  "feature/us-21-contain-failed-jobs:7"
  "feature/us-39-request-and-job-limits:8"
  "feature/us-28-integration-system-tests:9"
  "feature/us-30-load-test:12"
)

mapfile -t FILES < <(ls "$PATCHES"/*.patch | sort)
prev=0
for entry in "${PLAN[@]}"; do
  branch="${entry%%:*}"; last="${entry##*:}"
  if git show-ref --verify --quiet "refs/heads/$branch"; then echo "skip: $branch already exists"; prev=$last; continue; fi
  git checkout -q -b "$branch"
  for ((i=prev; i<last; i++)); do
    git am --quiet --3way "${FILES[$i]}" || { echo "Patch failed: ${FILES[$i]}"; git am --abort || true; exit 1; }
  done
  prev=$last
  echo "created: $branch"
  if $PUSH; then git push -u origin "$branch"; fi
done
git checkout -q "$BASE"
echo; echo "Done. Branches in your clone:"; git branch --list 'feature/us-*'
