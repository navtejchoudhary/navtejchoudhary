#!/usr/bin/env bash
# Usage:  ./setup.sh <github-username> [linkedin-url]
# Fills in your username, then pushes everything to github.com/<you>/<you>
set -euo pipefail

USER_NAME="${1:-}"
LINKEDIN="${2:-}"

if [ -z "$USER_NAME" ]; then
  echo "❌  Give your GitHub username:  ./setup.sh your-username [linkedin-url]"
  exit 1
fi

# 1) Put your username (and LinkedIn) into the README
perl -pi -e "s/__USERNAME__/${USER_NAME}/g" README.md
if [ -n "$LINKEDIN" ]; then
  perl -pi -e "s#__LINKEDIN__#${LINKEDIN}#g; s#<!--LINKEDIN-->##g" README.md
else
  perl -ni -e 'print unless /<!--LINKEDIN-->/' README.md   # no URL → drop the badge
fi

# 2) Commit and push
git init -q
git checkout -q -B main
git add -A
git commit -q -m "feat: profile README with animated banner, stats and contribution snake"
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/${USER_NAME}/${USER_NAME}.git"
git push -u origin main

echo ""
echo "✅  Pushed. Open https://github.com/${USER_NAME}"
echo "👉  Last step: https://github.com/${USER_NAME}/${USER_NAME}/actions → 'Generate contribution snake' → Run workflow"
