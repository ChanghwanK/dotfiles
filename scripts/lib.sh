#!/usr/bin/env bash
# lib.sh — shared helpers for bootstrap scripts

set -euo pipefail

# Colors
_R='\033[0m'
_B='\033[1m'
_G='\033[32m'
_Y='\033[33m'
_C='\033[36m'
_RED='\033[31m'

log_step() { printf "${_B}${_C}▶ %s${_R}\n" "$*"; }
log_info() { printf "  ${_G}✓${_R} %s\n" "$*"; }
log_warn() { printf "  ${_Y}⚠${_R} %s\n" "$*"; }
log_ok()   { printf "${_B}${_G}✔ %s${_R}\n" "$*"; }
log_err()  { printf "${_RED}✖ %s${_R}\n" "$*" >&2; }

has() { command -v "$1" &>/dev/null; }

DOTFILES="${DOTFILES:-$HOME/.dotfiles}"
