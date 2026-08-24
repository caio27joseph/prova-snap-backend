#!/usr/bin/env bash
# Worktree helper — conventions in docs/WORKTREES.md.
# Worktrees live OUTSIDE the repo (../<repo>.wt/<branch>) so tooling that walks
# the tree (pytest, ruff, git status) never sees a nested checkout.
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
REPO_NAME=$(basename "$ROOT")
WT_BASE="$(dirname "$ROOT")/${REPO_NAME}.wt"

usage() {
  cat <<EOF
Usage: scripts/wt.sh <command>

  new <branch> [base]   create worktree + branch (base defaults to main),
                        copy local .env, run uv sync
  list                  list all worktrees
  rm <branch>           remove a worktree safely (refuses if dirty or unmerged;
                        the branch itself is kept — see COMMIT_STRATEGY.md)
EOF
  exit 1
}

cmd=${1:-}
case "$cmd" in
  new)
    branch=${2:?usage: wt.sh new <branch> [base]}
    base=${3:-main}
    dir="$WT_BASE/$branch"
    [ -e "$dir" ] && { echo "error: $dir already exists"; exit 1; }

    if git show-ref --verify --quiet "refs/heads/$branch"; then
      git worktree add "$dir" "$branch"
    else
      git worktree add -b "$branch" "$dir" "$base"
    fi

    # .env is gitignored (machine-local port overrides) — without this copy the
    # worktree's app/tests would silently target the default port 5432.
    [ -f "$ROOT/.env" ] && cp "$ROOT/.env" "$dir/.env" && echo "copied .env"

    (cd "$dir" && uv sync --quiet) && echo "uv sync done"

    cat <<EOF

worktree ready: $dir
  cd $dir
  uv run uvicorn app.main:app --reload --port <PICK-A-FREE-PORT>

Do NOT run 'docker compose up' inside the worktree — it would spawn a second
Postgres stack and collide on the host port. The shared instance managed from
$ROOT serves all worktrees (see docs/WORKTREES.md).
EOF
    ;;
  list)
    git worktree list
    ;;
  rm)
    branch=${2:?usage: wt.sh rm <branch>}
    dir="$WT_BASE/$branch"
    [ -d "$dir" ] || { echo "error: no worktree at $dir"; exit 1; }

    if [ -n "$(git -C "$dir" status --porcelain)" ]; then
      echo "error: worktree has uncommitted changes — commit or discard first"
      exit 1
    fi
    if ! git merge-base --is-ancestor "$branch" main; then
      echo "error: branch '$branch' is not merged into main — merge it first"
      echo "       (per COMMIT_STRATEGY.md: from the main checkout, git merge --no-ff $branch)"
      exit 1
    fi

    git worktree remove "$dir"
    git worktree prune
    echo "worktree removed; branch '$branch' kept (delivery narrative)"
    ;;
  *)
    usage
    ;;
esac
