#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# lmchat.py - Terminal LLM Chat Client
# Copyright (c) 2026 Marcus Firmus. Licensed under the MIT License.
#
import argparse
import json
import os
import sys
import yaml
import formatting as fm
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ==========================================
# ENVIRONMENT AND FILE CONFIGURATION
# ==========================================
APP_DIR = Path(
   os.environ.get(
	   "LMCHAT_HOME",
	   str(Path.home() / ".lmchat")
   )
)

STATE_FILE = APP_DIR / "state.yaml"
REGISTRY_FILE = APP_DIR / "registry.yaml"
ALIASES_FILE = APP_DIR / "aliases.yaml"
CONFIG_FILE = APP_DIR / "config.yaml"
LOG_FILE = APP_DIR / "chat.jsonl"
IS_TTY = False

# Custom PyYAML dumper for multi‑line strings (YAML aesthetics)
def pyyaml_str_representer(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)
yaml.add_representer(str, pyyaml_str_representer)

# ==========================================
# HELPER FUNCTIONS FOR FILES AND ENVIRONMENT
# ==========================================
def init_env():
    global IS_TTY

    """Check terminal"""
    IS_TTY = sys.stdout.isatty()

    """Initialize directory structure and default files in ~/.lmchat"""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    
    if not STATE_FILE.exists():
        save_yaml(STATE_FILE, {
            "default_system_prompt": "You are a helpful assistant.",
            "default_model": "ollama/gemma3:4b",
            "default_chat": "default_chat.yaml"
        })
    if not ALIASES_FILE.exists():
        save_yaml(ALIASES_FILE, { 
            "lite": "gemini/gemini-flash-lite-latest",   
            "flash": "gemini/gemini-flash-latest",
            "gptoss": "ollama/gpt-oss:120b-cloud",
            "local": "ollama/gemma3:4b",
            "auto": "openrouter/openrouter/auto",
            "free": "openrouter/openrouter/free",
            "gpt": "openrouter/openai/gpt-chat-latest",
            "haiku": "openrouter/anthropic/claude-haiku-4.5" 
        })

    if not REGISTRY_FILE.exists():
        save_yaml(REGISTRY_FILE, {})
    if not CONFIG_FILE.exists():
        # Default pager (less). -F (quit if one screen), -R (colors), -X (no clear)
        save_yaml(CONFIG_FILE, {
            "pager": "less -FRX", 
            "padding": 4, 
            "line_length": 90
        })


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def save_yaml(path: Path, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def log_interaction(chat_name, model, prompt_tokens, completion_tokens, cost):
    """Log an event to the JSONL file"""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chat": str(chat_name),
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost": cost
    }
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry) + '\n')

def get_iso_time():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()

# ==========================================
# MAIN PROGRAM LOGIC
# ==========================================
class LMChat:
    def __init__(self, args):
        self.args = args
        self.state = load_yaml(STATE_FILE)
        self.registry = load_yaml(REGISTRY_FILE)
        self.aliases = load_yaml(ALIASES_FILE)
        self.config = load_yaml(CONFIG_FILE)
        
        # Apply CLI configuration overrides
        self._apply_config_overrides()

        self.cwd = str(Path.cwd())

        self._output_string = None     # Function that writes to `pager` or directly to `stdout`
        self._output_flush = None      # Appropriate "flush"
        self._pager = None             # Pager object, if used
        self._coloring = True          # Whether coloring is enabled
        self._text_formatter = None    # Object that wraps lines and adds indentation
        
        self.chat_path = None
        self.chat_yaml = None
        self._resolve_chat_path()
        self._resolve_metadata()

    def _apply_config_overrides(self):
        """Overrides configuration parameters based on CLI arguments."""
        # 1. Handle dedicated --no-pager flag
        if getattr(self.args, "no_pager", False):
            self.config["pager"] = ""

        # 2. Handle generic -o / --option key=value overrides
        if self.args.option:
            for opt in self.args.option:
                if "=" not in opt:
                    print(f"Warning: Ignored invalid option format '{opt}'. Use key=value.")
                    continue
                
                key, val_str = opt.split("=", 1)
                key = key.strip()
                
                # Use yaml.safe_load to automatically parse types (int, float, bool, null, str)
                try:
                    parsed_val = yaml.safe_load(val_str)
                except Exception:
                    parsed_val = val_str  # Fallback to raw string if parsing fails

                self.config[key] = parsed_val

    def _init_printing(self, formatter: bool):
        self._coloring = IS_TTY

        if IS_TTY and not self.args.raw:
            pager_cmd = self.config.get("pager", "less -FRX")

            # This "if" is needed because the user may deliberately disable the pager in the config.
            if pager_cmd:
                self._pager = subprocess.Popen(pager_cmd.split(), stdin=subprocess.PIPE, text=True)

                def _print_function(s):
                    self._pager.stdin.write(s)

                def _flush_function():
                    self._pager.stdin.flush()

                self._output_string = _print_function
                self._flush_function = _flush_function

        if not self._output_string:        
            def _plain_print_function(s):
                print(s, end="")

            def _plain_flush_function():
                sys.stdout.flush()

            self._output_string = _plain_print_function
            self._flush_function = _plain_flush_function

        if formatter:
            padding = int(self.config.get("padding", 4))
            linlen  = int(self.config.get("line_length", 90))

            if padding or linlen:
                self._text_formatter = fm.TextFormatter(padding, linlen, self._output_string, self._flush_function)

    def _resolve_chat_path(self):
        # If temporary mode is selected and no file is given via -c/-C,
        # use the global "trash" file in ~/.lmchat/temp_trash.yaml
        if self.args.temp and not (self.args.c or self.args.C):
            filename = str(APP_DIR / "temp_trash.yaml")
        else:
            filename = self.args.c or self.args.C
        
            if not filename:
                 filename = self.registry.get(self.cwd, self.state.get("default_chat", "default.yaml"))

        path_parts = Path(filename).parts
        base_name = path_parts[-1]
        if "." not in base_name:
            filename += ".yaml"

        if "/" not in filename and "\\" not in filename:
            self.chat_path = Path.cwd() / filename
        else:
            self.chat_path = Path(filename).resolve()

        if self.args.C:
            self.state["default_chat"] = self.chat_path.name
            save_yaml(STATE_FILE, self.state)

        if not self.args.temp:
            if self.args.C:
                self.state["default_chat"] = self.chat_path.name
                save_yaml(STATE_FILE, self.state)

            self.registry[self.cwd] = str(self.chat_path)
            save_yaml(REGISTRY_FILE, self.registry)

    def _resolve_metadata(self):
        self.chat_yaml = load_yaml(self.chat_path)
        
        if not self.chat_yaml:
            self.chat_yaml = {
                "version": 1,
                "metadata": {
                    "model": None,
                    "system_prompt": None,
                    "created": get_iso_time(),
                    "updated": get_iso_time()
                },
                "messages": []
            }

        meta = self.chat_yaml["metadata"]

        raw_model = self.args.m or self.args.M or meta.get("model") or self.state.get("default_model")
        self.model = self.aliases.get(raw_model, raw_model)
        
        if self.args.M:
            self.state["default_model"] = self.model
            save_yaml(STATE_FILE, self.state)
            
        self.sys_prompt = self.args.s or self.args.S or meta.get("system_prompt") or self.state.get("default_system_prompt")
        
        if self.args.S:
            self.state["default_system_prompt"] = self.sys_prompt
            save_yaml(STATE_FILE, self.state)

        meta["model"] = self.model
        meta["system_prompt"] = self.sys_prompt
        meta["updated"] = get_iso_time()

    def print_verbose(self):
        if self.args.verbose:
            print(f"Chat file : {self.chat_path}")
            print(f"Model     : {self.model}")
            print(f"Sys Prompt: {self.sys_prompt[:50]}...\n")
            print(f"Config    : {self.config}\n")

    def format_message_header(self, msg):
        if self._coloring:
            return self.format_string(f"\n[bold white]**{msg['role'].upper()}** ── [{msg.get('timestamp','-')}] ── {msg.get('model','')}[/bold white]\n\n")
        else:
            return f"\n**{msg['role'].upper()}** ── [{msg.get('timestamp','-')}] ── {msg.get('model','')}\n\n"

    def format_message_content(self, msg):
        padding = int(self.config.get("padding", 4))
        linlen  = int(self.config.get("line_length", 90))

        if self._coloring:
            ret = fm.markdown(msg['content'], max(linlen, 12), padding)
        else:
            ret = msg['content']
        return ret

    def format_string(self, s):
        return fm.richprint(s, markup=self._coloring)

    def format_file_header(self):
        if self._coloring:
           return (f"[cyan]*** CHAT FILE  [b]{self.chat_path}[/b] ***[/cyan]\n" +
                   f"[cyan]*** model  [b]{self.chat_yaml.get('metadata')['model']}[/b] ***[/cyan]\n")
        else:
           return (f"*** CHAT FILE  {self.chat_path} ***\n" +
                   f"*** model  {self.chat_yaml.get('metadata')['model']} ***\n")

    def view_chat(self):
        self._init_printing(formatter=False)

        if not self.chat_yaml.get("messages"):
            print(self.format_string("[dim text]Chat is empty.[/]"))
            return

        if not self.args.raw:
            fhdr = self.format_file_header()
            self._output_string( self.format_string(fhdr) + '\n' )

        for msg in self.chat_yaml["messages"]:
            header = self.format_message_header(msg)
            self._output_string(header)

            content = self.format_message_content(msg)
            self._output_string(content)

        self._output_string("\n")    

    def do_chat(self, user_content):
        from litellm import completion, cost_per_token

        self._init_printing(formatter=not self.args.raw)

        messages = [{"role": "system", "content": self.sys_prompt}]

        if self.args.temp:
            self.chat_yaml["messages"] = []

        for msg in self.chat_yaml.get("messages", []):
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        messages.append({"role": "user", "content": user_content})
        
        user_message = {"role": "user", "content": user_content, "timestamp": get_iso_time()}
        self.chat_yaml["messages"].append(user_message)
        if not self.args.raw:
            user_header = self.format_message_header(user_message)
            self._output_string(user_header)
            user_content_formatted = self.format_message_content(user_message)
            self._output_string(user_content_formatted)

        # Configura $response_format for JSON / Structured Outputs
        response_format = None

        if self.args.json_schema:
            schema_arg = self.args.json_schema.strip()
            # If standard file path provided, load from file
            if os.path.exists(schema_arg):
                with open(schema_arg, 'r', encoding='utf-8') as f:
                    if schema_arg.endswith(('.yaml', '.yml')):
                        schema_data = yaml.safe_load(f)
                    else:
                        schema_data = json.load(f)
            else:
                try:
                    schema_data = json.loads(schema_arg)
                except json.JSONDecodeError as e:
                    print(f"JSON parsing error for --json-schema: {e}")
                    sys.exit(1)

            # Normalize format for LiteLLM / OpenAI Structured Outputs
            if isinstance(schema_data, dict) and "type" in schema_data and "json_schema" in schema_data:
                response_format = schema_data
            elif isinstance(schema_data, dict) and "name" in schema_data and "schema" in schema_data:
                response_format = {"type": "json_schema", "json_schema": schema_data}
            else:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "custom_schema",
                        "schema": schema_data
                    }
                }
        elif self.args.json:
            response_format = {"type": "json_object"}
            # Ensure "JSON" word exists in prompt to prevent OpenAI API validation errors
            has_json = any("json" in m["content"].lower() for m in messages)
            if not has_json:
                messages[0]["content"] += " The answer must be valid JSON object"

        full_response = ""
        prompt_tokens = 0
        completion_tokens = 0

        try:
            assistant_message = {"role": "assistant", "model": self.model}
            if not self.args.raw:
                assistant_header = self.format_message_header(assistant_message)
                self._output_string(assistant_header)

            completion_kwargs = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                "num_ctx": 32768
            }
            if response_format:
                completion_kwargs["response_format"] = response_format
                
            max_tokens = self.args.max_tokens if self.args.max_tokens is not None else self.config.get("max_tokens")
            if max_tokens is not None:
                completion_kwargs["max_tokens"] = int(max_tokens)

            response = completion(**completion_kwargs)
            
            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                full_response += content

                if self._text_formatter:
                    self._text_formatter.output(content)
                else:
                    self._output_string(content)
                
                if hasattr(chunk, 'usage') and chunk.usage:
                    prompt_tokens = chunk.usage.get("prompt_tokens", 0)
                    completion_tokens = chunk.usage.get("completion_tokens", 0)

        except Exception as e:
            print(f"Communication error with LLM: {e}")
            sys.exit(1)

        if self.args.raw and full_response and not full_response.endswith('\n'):
            self._output_string('\n')

        self.chat_yaml["messages"].append({
            "role": "assistant",
            "model": self.model,
            "content": full_response,
            "timestamp": get_iso_time(),
            "completion_tokens": completion_tokens
        })
        save_yaml(self.chat_path, self.chat_yaml)

        cost = 0.0
        try:
            cost = cost_per_token(model=self.model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
        except Exception:
            pass
            
        log_interaction(
            self.chat_path.name,
            self.model,
            prompt_tokens,
            completion_tokens,
            cost
        )

        if self._text_formatter:
            self._text_formatter.output("\n")
            self._text_formatter.flush()

def main():
    init_env()
    
    parser = argparse.ArgumentParser(
        description="Terminal LLM client (lmchat)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Chat handling
    parser.add_argument("-c", type=str, metavar="FILE", help="Chat file (opens or creates a new one)")
    parser.add_argument("-C", type=str, metavar="FILE", help="Chat file (opens/creates and sets as default)")
    
    # Model handling
    parser.add_argument("-m", type=str, metavar="MODEL", help="Model or alias (e.g., 'g2b')")
    parser.add_argument("-M", type=str, metavar="MODEL", help="Model or alias (sets as default)")
    
    # System prompt handling
    parser.add_argument("-s", type=str, metavar="PROMPT", help="Set system prompt for the current session")
    parser.add_argument("-S", type=str, metavar="PROMPT", help="Set system prompt and save as default")
    
    parser.add_argument("-n", "--max-tokens", type=int, metavar="INT", help="Output tokens limit")

    # JSON & Format options
    parser.add_argument(
        "-j", "--json", 
        action="store_true", 
        help="Enforce JSON mode response"
    )
    parser.add_argument(
        "-J", "--json-schema", "--schema", 
        metavar="SCHEMA_OR_FILE", 
        help="Enforce a strict JSON output schema (accepts a JSON Schema string or a path to a .json/.yaml file)"
    )
    
    # Temporary chat handling
    parser.add_argument("-t", "--temp", action="store_true", help="Temporary mode: does not update registry or state. Uses a temporary file unless -c is provided.")
    
    # Interface options
    parser.add_argument("-p", "--print", action="store_true", help="Force READ‑ONLY/VIEW mode (do not ask for input)")
    parser.add_argument("-r", "--raw", action="store_true", help="Show only the raw text of the last reply")
    parser.add_argument("-v", "--verbose", action="store_true", help="Display details of configuration decisions")
    
    # Rendering options (toggles)
    parser.add_argument("-R", "--no-rich", action="store_true", help="Disable Markdown rendering in view mode")
    parser.add_argument("--no-pager", action="store_true", help="Disable pager for this run (useful for fzf preview)")

    # Generic Configuration Overrides
    parser.add_argument("-o", "--option", action="append", metavar="KEY=VALUE", help="Override config parameter (can be used multiple times, e.g. -o padding=0)")
    
    # Prompt content
    parser.add_argument("prompt", nargs="*", help="Content of the new message (joined with stdin)")

    args = parser.parse_args()

    app = LMChat(args)
    app.print_verbose()

    # Collect Prompt (CLI + Stdin)
    user_input_parts = []
    
    if args.prompt:
        user_input_parts.append(" ".join(args.prompt))
        
    if not sys.stdin.isatty():
        stdin_content = sys.stdin.read().strip()
        if stdin_content:
            user_input_parts.append(stdin_content)
            
    final_user_input = "\n\n".join(user_input_parts).strip()

    mode_view = args.print or (not final_user_input and sys.stdin.isatty())

    try:
        if mode_view:
            app.view_chat()
        else:
            if not final_user_input:
               print("No question/prompt provided. Run with -h to see help.")
               return
            app.do_chat(final_user_input)
    except BrokenPipeError:
        pass
    finally:
        if app._pager:
            if app._pager.stdin:
                app._pager.stdin.close()
            app._pager.wait()

if __name__ == "__main__":
    main()
