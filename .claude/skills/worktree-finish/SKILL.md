---
name: worktree-finish
description: Close a finished work block - merge its branch into main with --no-ff and remove the worktree. Use when a Parte block is done, tests pass, and the user wants to merge/close/finish the branch.
---

# Finishing a work block

Preconditions (all mandatory, in order):

1. Working tree clean — every change committed **with explicit approval**
   (CLAUDE.md rule).
2. Test suite green inside the worktree (`uv run pytest`); `main` only takes
   merges that keep it stable (COMMIT_STRATEGY.md).
3. Ask the user before merging — a merge is a commit.

Then, from the **primary checkout** (not the worktree):

```bash
cd /home/cj/Documents/prova-snap-backend
git merge --no-ff <branch> -m "merge: <block summary>"
scripts/wt.sh rm <branch>     # refuses if dirty or unmerged; keeps the branch
```

Branches are never deleted before delivery — the visible branch structure in
`git log --graph` is part of the evaluation narrative.
