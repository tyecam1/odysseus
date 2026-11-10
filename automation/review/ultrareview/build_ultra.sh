#!/usr/bin/env bash
# build_ultra.sh - build a size-eligible Ultrareview candidate from recent work.
# Usage: build_ultra.sh CLONE DEFAULT_BRANCH OLD_BASE_SHA TAG MERGES_FILE PATHS_FILE [CONTRACT_FILE] [--push]
#   integ = origin/DEFAULT + normal merges of every branch in MERGES_FILE
#           (a conflicting branch is aborted and reported, never forced)
#   base  = integ with every pathspec in PATHS_FILE rewound to OLD_BASE_SHA
#   head  = base + one commit restoring the exact integ tree (+ the contract file)
# The PR head->base diff then contains only the selected paths' changes since
# OLD_BASE_SHA, merged or not, while the whole repository stays available as context.
# Branches: ultra/TAG-integ, ultra/TAG-base, ultra/TAG-head. Synthetic; never merge them.
set -euo pipefail
CLONE=$1; DEF=$2; OLD=$3; TAG=$4
MERGES=$(realpath "$5"); PATHS=$(realpath "$6")
CONTRACT=${7:-}; PUSH=${8:-}
if [ -n "$CONTRACT" ]; then CONTRACT=$(realpath "$CONTRACT"); fi
name=$(basename "$(git -C "$CLONE" remote get-url origin)" .git)
WT=/home/agent/aoteru-worktrees/ultra-$TAG-$name
git -C "$CLONE" fetch -q origin "+refs/heads/*:refs/remotes/origin/*"
if [ -d "$WT" ]; then git -C "$CLONE" worktree remove --force "$WT"; fi
for b in integ base head; do git -C "$CLONE" branch -q -D "ultra/$TAG-$b" 2>/dev/null || true; done
git -C "$CLONE" worktree add -q -b "ultra/$TAG-integ" "$WT" "origin/$DEF"
cd "$WT"
echo "default $DEF @ $(git rev-parse HEAD)  old-base $OLD"
while read -r br; do
  [ -z "$br" ] && continue
  case $br in \#*) continue;; esac
  sha=$(git rev-parse "origin/$br")
  if git merge -q --no-ff --no-edit "origin/$br" >/dev/null 2>&1; then
    echo "MERGED   $br $sha"
  else
    echo "CONFLICT $br $sha :: $(git diff --name-only --diff-filter=U | tr '\n' ' ')"
    git merge --abort
  fi
done < "$MERGES"
INTEG=$(git rev-parse HEAD)
git checkout -q -b "ultra/$TAG-base"
while read -r p; do
  [ -z "$p" ] && continue
  case $p in \#*) continue;; esac
  git rm -rq --ignore-unmatch -- "$p" >/dev/null
  if git cat-file -e "$OLD:$p" 2>/dev/null; then git checkout -q "$OLD" -- "$p"; fi
done < "$PATHS"
git commit -q -m "review-base: rewind selected paths to $OLD (synthetic, never merge)"
BASE=$(git rev-parse HEAD)
HEAD_C=$(git commit-tree "$INTEG^{tree}" -p "$BASE" -m "review-head: restore integration tree $INTEG (synthetic, never merge)")
git checkout -q -b "ultra/$TAG-head" "$HEAD_C"
if [ -n "$CONTRACT" ] && [ -f "$CONTRACT" ]; then
  cp "$CONTRACT" ULTRAREVIEW_CONTRACT.md
  git add ULTRAREVIEW_CONTRACT.md
  git commit -q -m "review: ultrareview contract (synthetic, never merge)"
fi
echo "integ $INTEG"; echo "base  $BASE"; echo "head  $(git rev-parse HEAD)"
git diff --numstat "ultra/$TAG-base" "ultra/$TAG-head" | sort -k1,1nr | head -"${SHOW:-200}"
read -r NF NL < <(git diff --numstat "ultra/$TAG-base" "ultra/$TAG-head" | awk -F'\t' '{a+=$1+$2;n++} END{print n, a}')
echo "DIFF files=$NF lines=$NL (limit 500 files / 8000 lines)"
if [ "$PUSH" = "--push" ]; then
  if [ "$NL" -gt 7950 ] || [ "$NF" -gt 500 ]; then echo "NOT PUSHED: over budget"; exit 3; fi
  git push -q origin "ultra/$TAG-integ" "ultra/$TAG-base" "ultra/$TAG-head" && echo PUSHED
fi
