#!/usr/bin/env bash
# Publishes web/dist/ (already built -- see Makefile's web-gh-pages target)
# to the gh-pages branch via a git worktree, without touching the main
# checkout. Safe to re-run: creates the branch as an orphan on first run,
# otherwise updates the existing one. No-ops (doesn't push) if the build
# output is byte-identical to what's already published.
set -euo pipefail

cd "$(dirname "$0")/.."  # repo root

WORKTREE_DIR=".gh-pages-worktree"
BRANCH="gh-pages"

if [ ! -d "web/dist" ]; then
  echo "ERROR: web/dist/ not found -- run 'make web-gh-pages' first." >&2
  exit 1
fi

rm -rf "$WORKTREE_DIR"

if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  git fetch origin "$BRANCH:refs/remotes/origin/$BRANCH"
  git worktree add -B "$BRANCH" "$WORKTREE_DIR" "origin/$BRANCH"
else
  git worktree add --orphan -B "$BRANCH" "$WORKTREE_DIR"
fi

# Wipe the worktree's tracked contents (everything but .git), then copy in
# the fresh build -- handles files that were removed since the last publish.
find "$WORKTREE_DIR" -mindepth 1 -maxdepth 1 -not -name ".git" -exec rm -rf {} +
cp -r web/dist/. "$WORKTREE_DIR/"
touch "$WORKTREE_DIR/.nojekyll"  # GitHub Pages runs Jekyll by default; this is a prebuilt SPA, not a Jekyll site

cd "$WORKTREE_DIR"
git add -A
if git diff --cached --quiet; then
  echo "[publish_gh_pages] No changes -- gh-pages is already up to date."
else
  git commit -q -m "Deploy $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  git push -q origin "$BRANCH"
  echo "[publish_gh_pages] Published to gh-pages."
fi
cd - >/dev/null

git worktree remove "$WORKTREE_DIR" --force
