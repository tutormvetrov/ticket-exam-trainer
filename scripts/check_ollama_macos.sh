#!/usr/bin/env bash
set -euo pipefail

MODELS_PATH="${OLLAMA_MODELS:-$HOME/.ollama}"
OLLAMA_BIN="${OLLAMA_BIN:-$(command -v ollama || true)}"

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
curl -fsS "http://localhost:11434/api/tags"
echo

echo "Generate smoke test:"
curl -fsS "http://localhost:11434/api/generate" \
  -H "Content-Type: application/json" \
  -d '{"model":"mistral:instruct","prompt":"Answer in one short sentence: what is active recall?","stream":false}'
echo
