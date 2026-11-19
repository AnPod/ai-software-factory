#!/usr/bin/env bash
# End-to-end tests for install.sh. Runs in a temporary folder, needs no network.
# Checks are passed as strings and evaluated later, so single quotes are intended.
# shellcheck disable=SC2016,SC2034
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL="$REPO_DIR/install.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass=0
fail=0
ok() { echo "ok   $1"; pass=$((pass + 1)); }
bad() { echo "FAIL $1"; fail=$((fail + 1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

skills=()
for d in "$REPO_DIR"/skills/*/; do skills+=("$(basename "$d")"); done
first="${skills[0]}"

# 1. Dry run writes nothing.
mkdir "$TMP/p1"
"$INSTALL" --project "$TMP/p1" >/dev/null
check "dry run creates no files" '[ -z "$(ls -A "$TMP/p1")" ]'

# 2. Apply links every skill for the default harnesses.
"$INSTALL" --project "$TMP/p1" --apply >/dev/null
for s in "${skills[@]}"; do
  check "claude link for $s" '[ -L "$TMP/p1/.claude/skills/$s" ] && [ -f "$TMP/p1/.claude/skills/$s/SKILL.md" ]'
  check "agents link for $s" '[ -L "$TMP/p1/.agents/skills/$s" ]'
done

# 3. Running again is idempotent.
out="$("$INSTALL" --project "$TMP/p1" --apply)"
check "second run makes no changes" 'grep -q "Done: 0 change" <<<"$out"'

# 4. Existing folders that we did not create are left alone.
mkdir -p "$TMP/p2/.claude/skills/$first"
echo "mine" > "$TMP/p2/.claude/skills/$first/SKILL.md"
"$INSTALL" --project "$TMP/p2" --harness claude --apply >/dev/null
check "foreign folder is not overwritten" 'grep -q "^mine$" "$TMP/p2/.claude/skills/$first/SKILL.md"'

# 5. Copy mode marks copies, and uninstall removes only what we installed.
mkdir "$TMP/p3"
"$INSTALL" --project "$TMP/p3" --harness opencode --copy --apply >/dev/null
check "copy is a real folder" '[ -d "$TMP/p3/.opencode/skills/$first" ] && [ ! -L "$TMP/p3/.opencode/skills/$first" ]'
check "copy carries marker" '[ -f "$TMP/p3/.opencode/skills/$first/.aiwerk-installed" ]'
mkdir -p "$TMP/p3/.opencode/skills/someone-elses-skill"
"$INSTALL" --project "$TMP/p3" --harness opencode --uninstall --apply >/dev/null
check "uninstall removes our copies" '[ ! -e "$TMP/p3/.opencode/skills/$first" ]'
check "uninstall keeps other skills" '[ -d "$TMP/p3/.opencode/skills/someone-elses-skill" ]'

# 6. Aliases and the droid path.
mkdir "$TMP/p4"
"$INSTALL" --project "$TMP/p4" --harness codex,pi,copilot,droid --apply >/dev/null
check "codex, pi and copilot map to .agents" '[ -L "$TMP/p4/.agents/skills/$first" ]'
check "droid maps to .factory/skills" '[ -L "$TMP/p4/.factory/skills/$first" ]'

# 7. User scope respects HOME.
HOME="$TMP/home" "$INSTALL" --scope user --harness claude --apply >/dev/null
check "user scope installs into HOME" '[ -L "$TMP/home/.claude/skills/$first" ]'

# 8. Bad input fails.
check "unknown harness is rejected" '! "$INSTALL" --harness nope >/dev/null 2>&1'

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
