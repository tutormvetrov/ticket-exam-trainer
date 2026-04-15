#!/usr/bin/env bash
set -euo pipefail

MODELS_PATH="${OLLAMA_MODELS:-$HOME/.ollama}"
OLLAMA_BIN="${OLLAMA_BIN:-$(command -v ollama || true)}"
PREFERRED_MODEL="qwen3:8b"
export OLLAMA_MODELS="$MODELS_PATH"

echo "macOS Ollama check"
echo "OLLAMA_MODELS: $MODELS_PATH"

if [[ -z "$OLLAMA_BIN" ]]; then
  echo "ollama CLI not found in PATH"
  echo "Install Ollama first. See https://docs.ollama.com/macos"
  exit 1
fi

echo "Ollama executable: $OLLAMA_BIN"
echo "Version:"
"$OLLAMA_BIN" --version

if ! curl -fsS "http://localhost:11434/api/tags" >/dev/null 2>&1; then
  echo "Starting Ollama service"
  if [[ -d "/Applications/Ollama.app" ]]; then
    open -a Ollama
  else
    "$OLLAMA_BIN" serve >/tmp/ollama-serve.log 2>&1 &
  fi
  sleep 8
fi

echo "Model list:"
"$OLLAMA_BIN" list

echo "API tags:"
TAGS_JSON="$(curl -fsS "http://localhost:11434/api/tags")"
printf '%s\n' "$TAGS_JSON"
echo

SMOKE_MODEL="$PREFERRED_MODEL"
if ! printf '%s' "$TAGS_JSON" | grep -F "\"name\":\"$PREFERRED_MODEL\"" >/dev/null 2>&1; then
  FALLBACK_MODEL="$("$OLLAMA_BIN" list | awk 'NR > 1 && ($1 ~ /^qwen3:/ || $1 ~ /^qwen:/ || $1 ~ /qwen/) { print $1; exit }')"
  if [[ -z "$FALLBACK_MODEL" ]]; then
    FALLBACK_MODEL="$("$OLLAMA_BIN" list | awk 'NR > 1 && $1 != "" { print $1; exit }')"
  fi
  if [[ -n "$FALLBACK_MODEL" ]]; then
    SMOKE_MODEL="$FALLBACK_MODEL"
    echo "Preferred model '$PREFERRED_MODEL' not found. Using smoke-test fallback: $SMOKE_MODEL"
  fi
fi

echo "Generate smoke test:"
curl -fsS "http://localhost:11434/api/generate" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$SMOKE_MODEL\",\"prompt\":\"Answer in one short sentence: what is active recall?\",\"stream\":false}"
echo
