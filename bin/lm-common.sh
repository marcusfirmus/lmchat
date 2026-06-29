#! /bin/bash
set -u

LM_DIR="${LMCHAT_HOME:-$HOME/.lmchat}"
EDITOR="${EDITOR:-vi}"
KEYS_FILE="$LM_DIR/init_keys.sh"

#  Place Your API keys initialization here:
if [ -f "$KEYS_FILE" ]; then
    source "$KEYS_FILE"
else
    echo "Warning: File '$KEYS_FILE' not found."
    echo "Please create this file and add your API keys to it."
fi
