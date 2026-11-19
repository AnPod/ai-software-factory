#!/usr/bin/env bash
# Install AI Werk Skills into the skill folders of your coding agents.
#
# Dry run by default: it prints what it would do and changes nothing.
# Add --apply to make the change. It links (or copies) skill folders, nothing else:
# no downloads, no network calls, no changes outside the target skill folders.
#
# Usage:
#   ./install.sh [--harness LIST] [--scope project|user] [--project DIR]
#                [--copy] [--apply] [--uninstall]
#
#   --harness   comma-separated: claude, agents, opencode, cursor, gemini, droid, all
#               (codex and pi are aliases for agents). Default: claude,agents
#   --scope     project (default): into DIR/.claude/skills etc.
#               user: into your home folder, for every project
#   --project   project folder for --scope project. Default: current folder
#   --copy      copy instead of symlink (symlinks follow `git pull` updates)
#   --apply     make the changes. Without it nothing is written.
#   --uninstall remove skills this script installed (only links into this repo,
#               or copies that carry the .aiwerk-installed marker)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$REPO_DIR/skills"
MARKER=".aiwerk-installed"

harness="claude,agents"
scope="project"
project="$PWD"
mode="link"
apply=0
uninstall=0

die() { echo "error: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --harness) [ $# -ge 2 ] || die "--harness needs a value"; harness="$2"; shift 2 ;;
    --scope) [ $# -ge 2 ] || die "--scope needs a value"; scope="$2"; shift 2 ;;
    --project) [ $# -ge 2 ] || die "--project needs a value"; project="$2"; shift 2 ;;
    --copy) mode="copy"; shift ;;
    --apply) apply=1; shift ;;
    --uninstall) uninstall=1; shift ;;
    -h|--help) sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

case "$scope" in project|user) ;; *) die "--scope must be project or user" ;; esac
[ -d "$project" ] || die "project folder not found: $project"
project="$(cd "$project" && pwd)"

target_dir() {
  local h="$1"
  if [ "$scope" = "project" ]; then
    case "$h" in
      claude) echo "$project/.claude/skills" ;;
      agents) echo "$project/.agents/skills" ;;
      opencode) echo "$project/.opencode/skills" ;;
      cursor) echo "$project/.cursor/skills" ;;
      gemini) echo "$project/.gemini/skills" ;;
      droid) echo "$project/.factory/skills" ;;
    esac
  else
    case "$h" in
      claude) echo "$HOME/.claude/skills" ;;
      agents) echo "$HOME/.agents/skills" ;;
      opencode) echo "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills" ;;
      cursor) echo "$HOME/.cursor/skills" ;;
      gemini) echo "$HOME/.gemini/skills" ;;
      droid) echo "$HOME/.factory/skills" ;;
    esac
  fi
}

# Expand and de-duplicate the harness list.
harnesses=()
IFS=',' read -r -a requested <<< "$harness"
for h in "${requested[@]}"; do
  case "$h" in
    all) set -- claude agents opencode cursor gemini droid ;;
    codex|pi) set -- agents ;;
    claude|agents|opencode|cursor|gemini|droid) set -- "$h" ;;
    "") set -- ;;
    *) die "unknown harness: $h" ;;
  esac
  for x in "$@"; do
    case " ${harnesses[*]-} " in *" $x "*) ;; *) harnesses+=("$x") ;; esac
  done
done
[ "${#harnesses[@]}" -gt 0 ] || die "no harness selected"

run() {
  if [ "$apply" -eq 1 ]; then "$@"; else echo "  would run: $*"; fi
}

skills=()
for d in "$SKILLS_DIR"/*/; do
  [ -f "$d/SKILL.md" ] && skills+=("$(basename "$d")")
done
[ "${#skills[@]}" -gt 0 ] || die "no skills found in $SKILLS_DIR"

if [ "$apply" -eq 0 ]; then
  echo "Dry run. Nothing will be changed. Add --apply to install."
fi
echo "Skills: ${skills[*]}"
echo

changes=0
for h in "${harnesses[@]}"; do
  dest="$(target_dir "$h")"
  echo "[$h] $dest"
  for s in "${skills[@]}"; do
    src="$SKILLS_DIR/$s"
    dst="$dest/$s"
    if [ "$uninstall" -eq 1 ]; then
      if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
        run rm "$dst"; changes=$((changes + 1))
      elif [ -d "$dst" ] && [ -f "$dst/$MARKER" ]; then
        run rm -r "$dst"; changes=$((changes + 1))
      elif [ -e "$dst" ] || [ -L "$dst" ]; then
        echo "  skip $s: not installed by this script, left alone"
      fi
      continue
    fi
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
      echo "  ok   $s (already linked)"
      continue
    fi
    if [ -e "$dst" ] || [ -L "$dst" ]; then
      if [ "$mode" = "copy" ] && [ -f "$dst/$MARKER" ]; then
        run rm -r "$dst"
      else
        echo "  skip $s: $dst already exists and was not installed by this script"
        continue
      fi
    fi
    run mkdir -p "$dest"
    if [ "$mode" = "link" ]; then
      run ln -s "$src" "$dst"
    else
      run cp -R "$src" "$dst"
      run touch "$dst/$MARKER"
    fi
    changes=$((changes + 1))
  done
done

echo
if [ "$apply" -eq 1 ]; then
  echo "Done: $changes change(s)."
  if [ "$uninstall" -eq 0 ] && [ "$changes" -gt 0 ]; then
    echo "Next: open your coding agent in the project and ask it to use the aiwerk-init skill."
  fi
else
  echo "Dry run: $changes change(s) planned. Re-run with --apply to make them."
fi
