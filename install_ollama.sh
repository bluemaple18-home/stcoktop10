#!/bin/bash
echo "Installing Ollama..."
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Please install Homebrew first."
    exit 1
fi
brew install ollama
echo "Ollama installed."
