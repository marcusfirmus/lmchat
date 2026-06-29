# lmchat

<p align="center">
  <img src="demo.svg" alt="lmchat demo">
</p>

A lightweight, Unix-philosophical terminal LLM client designed for direct chat, git-style workflow, and AI-assisted scripting.

## Philosophy & Core Concepts

Unlike web-based or heavy desktop LLM clients, `lmchat` is designed to feel like a native Unix tool (like `git` or `grep`):

*   **Directory-Based Registry (CWD as State):** Your current working directory (`pwd`) determines your active conversation. If you are in `~/projects/engine`, `lmchat` automatically loads and saves the chat history associated with that directory.
*   **Pipeline Ready:** Fully supports standard input. `cat code.py | lmchat "refactor this"` works out of the box.
*   **Git Aesthetics:** Output is streamed and formatted as Markdown, then piped to your system's pager (like `less -FRX`) only if you are in a TTY.
*   **Transparent YAML Storage:** No hidden SQLite databases. Conversations, aliases, and settings are saved in clean, human-readable YAML files. You can easily `grep`, `fzf` or version-control your chats.

---

## Features

*   **Powered by LiteLLM:** Out-of-the-box support for 100+ providers (Ollama, Gemini, OpenRouter, OpenAI, Anthropic, etc.).
*   **Turn-Based CLI:** One execution equals one turn in the conversation.
*   **Hybrid Modes:** Seamlessly switch between persistent chats and temporary single-shot queries (`-t`).
*   **Smart Defaults:** Automatically falls back to system-wide or user-configured default models and system prompts if not specified in the current chat.
*   **Git-like Pager Integration:** Automatic rich Markdown rendering in the terminal with fallback to raw, unformatted stdout for scripts.

---

## Requirements & Installation

### Requirements
*   **Python 3.9+**
*   Libraries listed in `requirements.txt` (mainly `litellm`, `rich`, `pyyaml`)

### Installation Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/marcusfirmus/lmchat.git ~/lmchat
   ```

2. Set up the virtual environment and install dependencies:
   ```bash
   cd ~/lmchat
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Expose the helper scripts to your local `$PATH` (e.g., to `~/bin` or `~/.local/bin`):
   ```bash
   # Define your local bin directory
   BIN_DIR="$HOME/bin"
   mkdir -p "$BIN_DIR"

   # Create symlinks
   for script in lm-common.sh lmchat lmaliases lminfo lmregistry lmtmpcopy; do
       ln -sf "$PWD/bin/$script" "$BIN_DIR/$script"
   done
   ```
   
   **Note: Keep the cloned repo intact, as these are symlinks.**
   
---

## Configuration

On the first run, `lmchat` will automatically create a configuration directory structure in `~/.lmchat/`:

```
~/.lmchat/
├── config.yaml       # General settings (padding, line wrapping, pager)
├── aliases.yaml      # Model nicknames (e.g., "pro" -> "gemini/gemini-1.5-pro")
├── state.yaml        # Default system prompt, model, and active chat
├── registry.yaml     # Directory-to-chat mappings
└── init_keys.sh      # Your API keys and environment variables (ignored by git)
```

### Setting up API Keys

Edit `~/.lmchat/init_keys.sh` to export your keys:

```bash
export GOOGLE_API_KEY="your-gemini-api-key"
export OPENROUTER_API_KEY="your-openrouter-key"
# Optional: Ollama settings (not needed if running locally on standard port)
# export OLLAMA_API_BASE="http://localhost:11434"
```

> **Security Note:** Make sure your keys are protected. After editing, run `chmod 600 ~/.lmchat/init_keys.sh` so other users on the system cannot read them.

---

## Usage Examples

### 1. Standard Interactive Chat (CWD-bound)
Simply type your message. `lmchat` will resolve the chat history associated with your current directory:

```bash
$ lmchat "How to locate .wav files greater than 100MB on a Linux system?"
```
*Output will stream into your pager (e.g. `less`), rendered beautifully with Markdown.*

### 2. Raw Output (`-r` / `--raw`)
Useful when you want only the raw response text, perfect for quick CLI tasks or feeding to other tools:

```bash
$ lmchat -r "Write a quick oneliner to find IP addresses in log.txt using grep"
grep -E -o "([0-9]{1,3}\.){3}[0-9]{1,3}" log.txt
```

### 3. Pipeline Mode (Stdin)
`lmchat` automatically reads standard input if it's not a TTY:

```bash
$ diff old.py new.py | lmchat "Explain this diff in 3 bullet points"
```

### 4. Single-Shot / Temporary Queries (`-t`)
Ask a question without registering a persistent chat or polluting your project directory:

```bash
$ lmchat -t -s "Answer very short, in one word" "Capital of Peru"
Lima
```

### 5. Model Switching & Aliases
Quickly target a specific model or user-defined alias:

```bash
# Using a full identifier
$ lmchat -m ollama/gemma3:4b "What is 2+2?"

# Using an alias defined in aliases.yaml
$ lmchat -m pro "Write a complex regex..."
```

### 6. Persistent Settings (Capitalized Flags)
You can alter chat settings temporarily or permanently (using uppercase flags):

```bash
# Temporarily use a different model for this turn
$ lmchat -m haiku "Translate this to French"

# Change the model and save it as the new default
$ lmchat -M pro "Let's stick to the Pro model from now on"

# Set a persistent system prompt
$ lmchat -S "You are a senior Linux kernel developer. Reply succinctly." "How does epoll work?"
```

### 7. View Chat History
If you simply want to read the current conversation formatted in Markdown using your pager (without sending a new prompt):

```bash
$ lmchat -p
# Or equivalent (if standard input is empty and it's a TTY):
$ lmchat
```

---

## Helper Utilities ("lm" Menu)

All helper scripts start with the `lm` prefix, making autocomplete with `TAB` extremely comfortable:

*   `lmchat` - The main executable wrapper.
*   `lmaliases` - View or edit (`-e`) your model aliases.
*   `lminfo` - Display information about the current directory's active chat, model, and configuration.
*   `lmregistry` - View the list of registered directory-to-chat mappings.
*   `lmtmpcopy <dest.yaml>` - Promote your last temporary (`-t`) chat to a persistent conversation file.

---

## Future Roadmap

- [ ] **Context Truncation:** Options to trim chat history (`head`, `tail`, or range selection) to manage token usage.
- [ ] **Inline File Injection:** Easily inject local file contents via CLI options (e.g., `lmchat "Refactor this:" -f main.py`).
- [ ] **Output Extraction:** Auto-extract generated code blocks directly into target files (e.g., `-w output.py`).
- [ ] **JSON Mode Support:** Enforce JSON outputs for automation scripts.
- [ ] **Interactive CLI setup wizard** to make configuring API keys even easier.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
