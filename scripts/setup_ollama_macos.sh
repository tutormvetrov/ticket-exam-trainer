#!/usr/bin/env bash
set -euo pipefail

MODELS_PATH="${OLLAMA_MODELS:-$HOME/.ollama}"
OLLAMA_BIN="${OLLAMA_BIN:-$(command -v ollama || true)}"
export OLLAMA_MODELS="$MODELS_PATH"

echo "Preparing Ollama models directory: $MODELS_PATH"
mkdir -p "$MODELS_PATH"

if [[ -z "$OLLAMA_BIN" ]]; then
  if command -v brew >/dev/null 2>&1; then
    echo "Installing Ollama via Homebrew Cask"
    brew install --cask ollama
    OLLAMA_BIN="$(command -v ollama || true)"
  fi
fi

if [[ -z "$OLLAMA_BIN" ]]; then
  echo "Ollama CLI not found after auto-install attempt."
  echo "Install Ollama manually from https://docs.ollama.com/macos"
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

echo "Pulling qwen3:8b"
"$OLLAMA_BIN" pull qwen3:8b

echo "Installed models:"
"$OLLAMA_BIN" list

echo "API tags:"
curl -fsS "http://localhost:11434/api/tags"
echo
