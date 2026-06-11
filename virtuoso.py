#!/usr/bin/env python3
"""
Virtuoso CLI Agent – Phase 1
Commands: /generate, /plan, /search, /read, /glob, /status, /config, /exit
"""

import sys
import os
import argparse
import socket
import shutil
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=".*doesn't match a supported version.*")

sys.path.insert(0, str(Path(__file__).parent))

import yaml
from core.config import load_config, CONFIG_PATH
from core.logger import setup_logger
from core.llm_client import get_llm_client
from core.shimmy_manager import (
    find_shimmy_binary,
    install_shimmy,
    install_shimmy_help,
    is_shimmy_running,
    resolve_shimmy_model,
    start_shimmy,
    stop_shimmy,
)
from core.tools import has_ripgrep, grep, glob_files, read_file
from core.reasoning import TreeOfThoughts
from core.agents import Orchestrator
from core.sandbox import LightweightSandbox, is_dangerous, ask_permission
from core.memory import ProjectMemory, SlidingWindowSummarizer
from datetime import datetime
from core.expert import GeminiExpert
from core.conversation import build_conversation_prompt, max_conversation_exchanges
from core.gemini_models import DEFAULT_GEMINI_FLASH
from core.onboarding import run_onboarding_wizard
from core.presets import list_presets, preset_system_prompt
from core.profiles import apply_profile, list_profiles
from core.gemini_setup import (
    GEMINI_KEY_URL,
    get_gemini_api_key,
    has_gemini_api_key,
    mask_api_key,
    prompt_for_api_key,
    save_gemini_api_key,
)
from core.openai_setup import PROVIDER_PRESETS, apply_provider_preset, has_openai_api_key
from core.output_paths import write_code_output
from core.version import __version__

config = None
logger = None
llm_client = None
history = []
conversation_history = []
tot = None
orchestrator = None
sandbox = None
last_code = None
project_memory = None
summarizer = None
constitution = ""
expert = None


def _reconnect_llm() -> None:
    global llm_client, orchestrator, tot, config
    config = load_config()
    llm_cfg = config.get("llm", {})
    llm_client = get_llm_client(llm_cfg)
    tot = TreeOfThoughts(llm_client, max_depth=3, width=3, eval_threshold=0.4)
    orchestrator = Orchestrator(llm_client)


def init() -> bool:
    global config, logger, llm_client, tot, orchestrator, project_memory, summarizer, constitution, last_code, expert
    config = load_config()
    logger = setup_logger()
    logger.info("Virtuoso CLI Agent Phase 3 started")
    Path(".virtuoso").mkdir(exist_ok=True)
    llm_client = None

    try:
        # Create unified LLM client according to config.llm (falls back if necessary)
        llm_cfg = config.get("llm", {})
        llm_client = get_llm_client(llm_cfg)
        backend = llm_cfg.get("backend", "gemini-apikey")
        if backend == "shimmy":
            from core.shimmy_manager import is_shimmy_healthy, is_shimmy_running, resolve_shimmy_model

            port = llm_cfg.get("shimmy", {}).get("port", 8080)
            if not is_shimmy_running(port) or not is_shimmy_healthy(port):
                raise ConnectionError(f"Shimmy is not healthy on port {port}")
            model = resolve_shimmy_model(
                port=port,
                configured=llm_cfg.get("shimmy", {}).get("model", "auto"),
                preferred_path=llm_cfg.get("shimmy", {}).get("model_path"),
            )
            print(f"Shimmy ready on port {port} (model: {model}). First /generate may take up to a minute.")
            logger.info("Connected to Shimmy backend")
        elif backend in ("gemini-apikey", "gemini-flash", "gemini-pro", "gemini-oauth"):
            key = get_gemini_api_key(config) if backend != "gemini-oauth" else "(oauth)"
            if backend == "gemini-apikey" and not key:
                raise ConnectionError("No Gemini API key configured. Run /gemini setup")
            model = llm_cfg.get("gemini", {}).get("model", DEFAULT_GEMINI_FLASH)
            if backend == "gemini-apikey":
                print(f"Gemini ready (model: {model}, key: {mask_api_key(key)}). Type your prompt at >")
            else:
                print(f"Gemini ready (backend: {backend}, model: {model}). Type your prompt at >")
            logger.info("Connected to Gemini backend")
        elif backend == "openai":
            from core.openai_compat_client import resolve_openai_api_key

            oai_cfg = llm_cfg.get("openai", {})
            key = resolve_openai_api_key(oai_cfg)
            if not key:
                raise ConnectionError("No OpenAI-compatible API key. Run /openai setup")
            model = oai_cfg.get("model", "gpt-4o-mini")
            print(f"OpenAI-compatible API ready (model: {model}, key: {mask_api_key(key)}).")
            logger.info("Connected to OpenAI-compatible backend")
        tot = TreeOfThoughts(llm_client, max_depth=3, width=3, eval_threshold=0.4)
        orchestrator = Orchestrator(llm_client)
        # Initialize project memory and summarizer
        project_memory = ProjectMemory(".")
        constitution = project_memory.load_constitution()
        logger.info("Project constitution loaded")
        state = project_memory.load_state()
        last_code = state.get("last_code", "")
        summarizer = SlidingWindowSummarizer(llm_client, max_tokens=4000, summary_trigger=3000)
        # Initialize expert fallback if configured
        try:
            expert_cfg = config.get("expert", {})
            if expert_cfg.get("enabled", False):
                api_key = expert_cfg.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
                expert = GeminiExpert(api_key=api_key, max_failures_before_fallback=expert_cfg.get("max_failures_before_fallback", 2))
                if expert.is_available():
                    print("✅ Gemini expert fallback ready (free tier)")
                else:
                    expert = None
        except Exception:
            expert = None
        return True
    except Exception as e:
        backend = config.get("llm", {}).get("backend", "gemini-apikey")
        logger.error(f"LLM backend error ({backend}): {e}")
        if backend == "shimmy":
            print("Error: Shimmy backend is not ready.")
            print("  • Run /shimmy install then /shimmy start")
            print("  • Or /backend gemini-apikey after /gemini setup")
            print("  • Large local models (>2 GB) may fail on integrated GPUs")
        elif backend.startswith("gemini"):
            print(f"Error: Could not connect to Gemini ({e})")
            print(f"  • Run /gemini setup and paste a key from {GEMINI_KEY_URL}")
            print("  • Or set GEMINI_API_KEY in your environment")
        else:
            print(f"Error: Could not connect to LLM backend '{backend}': {e}")
        print("Virtuoso is running in setup mode — fix the backend with /gemini setup, /shimmy start, or /backend <name>.")
        return False


def get_sandbox():
    global sandbox
    if sandbox is None:
        sandbox = LightweightSandbox(timeout_sec=10, max_memory_mb=512, max_disk_mb=100)
    return sandbox


def cmd_clear():
    global conversation_history
    conversation_history.clear()
    print("Conversation history cleared.")


def _chat_exchange_limit() -> int:
    backend = config.get("llm", {}).get("backend", "")
    if backend == "shimmy":
        return min(3, max_conversation_exchanges(config))
    return max_conversation_exchanges(config)


def _system_context(extra: str = "") -> str:
    parts = []
    if constitution:
        parts.append(f"Project constitution:\n{constitution}")
    if extra:
        parts.append(extra)
    return "\n\n".join(parts) if parts else ""


def cmd_generate(prompt: str, preset: str = "", raw: bool = False):
    global conversation_history
    if not prompt:
        print("Usage: /generate <prompt>")
        return
    if llm_client is None:
        print("No LLM backend connected. Run /gemini setup, /shimmy start, or /backend <name>.")
        return
    logger.info(f"Generate: {prompt[:100]}")
    system_prompt = _system_context(preset_system_prompt(preset) or "")
    llm_prompt = prompt if raw else build_conversation_prompt(
        prompt,
        conversation_history,
        max_exchanges=_chat_exchange_limit(),
    )
    print("\n--- Response ---")
    full_response = []
    try:
        for chunk in llm_client.generate(llm_prompt, system_prompt=system_prompt or None):
            print(chunk, end="", flush=True)
            full_response.append(chunk)
    except Exception as exc:
        print(f"\n[Error: {exc}]")
        return
    print("\n--- End ---\n")
    assistant_text = "".join(full_response).strip()
    if not assistant_text:
        print(
            "No text returned. For cloud inference run /gemini setup, or retry after /shimmy start "
            "(first reply on integrated GPUs can take 1–2 minutes)."
        )
        return
    conversation_history.append({"role": "user", "content": prompt})
    conversation_history.append({"role": "assistant", "content": assistant_text})
    max_entries = max_conversation_exchanges(config) * 2
    if len(conversation_history) > max_entries:
        conversation_history[:] = conversation_history[-max_entries:]
    # Persist interaction to project memory
    try:
        project_memory.add_to_history({"role": "user", "content": prompt, "timestamp": str(datetime.now())})
        project_memory.add_to_history({"role": "assistant", "content": assistant_text, "timestamp": str(datetime.now())})
    except Exception:
        history.append(("user", prompt))
        history.append(("assistant", assistant_text))
        if len(history) > 20:
            history[:] = history[-20:]


def cmd_plan(problem: str):
    if not problem:
        print("Usage: /plan <problem>")
        return
    if tot is None:
        print("Backend not connected. Run /gemini setup or /profile local.")
        return
    logger.info(f"Planning for: {problem[:100]}")
    print("\n--- Thinking ---")
    best_node = tot.search(problem, initial_thought="Understand the problem and break it down.")
    if best_node:
        steps = tot.get_path(best_node)
        if steps and steps[0] == "Start":
            steps = steps[1:]
        print("\n--- Plan ---")
        for i, step in enumerate(steps, 1):
            print(f"{i}. {step}")
    else:
        print("Could not generate a valid plan. Try rephrasing the problem.")


def _parse_build_args(goal: str) -> tuple[str, str | None]:
    explicit_path = None
    rest = goal.strip()
    if rest.startswith("--save "):
        parts = rest.split(" ", 2)
        if len(parts) >= 2:
            explicit_path = parts[1]
            rest = parts[2] if len(parts) > 2 else ""
    return rest, explicit_path


def _save_build_code(code: str, goal: str, explicit_path: str | None = None) -> None:
    if not code or not code.strip():
        return
    try:
        written = write_code_output(code, goal, explicit_path=explicit_path)
        if written:
            print(f"\n💾 Saved to: {written}")
    except Exception as exc:
        print(f"\n⚠️ Could not save file: {exc}")


def cmd_save(path: str = ""):
    """Save last /build output. Usage: /save or /save C:\\path\\to\\file.py"""
    global last_code
    if not last_code:
        print("Nothing to save. Use /build first.")
        return
    explicit = path.strip() or None
    written = write_code_output(last_code, f"save to {explicit}" if explicit else "", explicit_path=explicit)
    if written:
        print(f"Saved to: {written}")
    elif explicit:
        print(f"Failed to save to: {explicit}")
    else:
        print("Usage: /save <full path>   e.g. /save C:\\Users\\you\\Desktop\\script.py")


def cmd_build(goal: str, cancel_check=None):
    goal_text, explicit_path = _parse_build_args(goal)
    if not goal_text:
        print("Usage: /build <goal>")
        print("       /build --save C:\\path\\file.py <goal>")
        print("Example: /build a python fraction solver on my desktop titled ai test math")
        return
    if orchestrator is None:
        print("Backend not connected. Run /gemini setup, /openai setup, or /profile local.")
        return
    logger.info(f"Build goal: {goal_text[:100]}")
    print(f"\n🚀 Building: {goal_text}\n")
    result = orchestrator.build(goal_text, context="", cancel_check=cancel_check)
    global last_code
    last_code = result.get("code", "")
    if result.get("error"):
        print(f"\n⚠️ Build stopped: {result['error']}")
        if result.get("completed_tasks"):
            print(f"Completed {result['completed_tasks']} of {len(result.get('plan', []))} tasks before failure.")
    if not last_code:
        if "error" in result:
            return
        print("No code was generated.")
        return
    try:
        state = project_memory.load_state()
        state["last_code"] = last_code
        project_memory.save_state(state)
    except Exception:
        pass
    print("\n📦 Final Code:\n")
    print(last_code)
    print("\n📊 Review Result:", "PASS" if result.get("success") else "FAIL")
    if result.get("review", {}).get("ISSUES"):
        print("Issues:", result["review"]["ISSUES"])
    _save_build_code(last_code, goal_text, explicit_path=explicit_path)
    if not result.get("success") and expert and not result.get("error"):
        try:
            print("\n🔁 Local attempts failed — trying Gemini expert fallback...")
            expert_code = expert.solve(goal_text, local_attempts=[], context=last_code or "")
            if expert_code:
                print("✨ Gemini provided a solution — applying and saving.")
                last_code = expert_code
                try:
                    state = project_memory.load_state()
                    state["last_code"] = last_code
                    project_memory.save_state(state)
                    project_memory.add_to_history({"role": "expert","content": expert_code, "timestamp": str(datetime.now())})
                except Exception:
                    pass
                print("\n📦 Expert Code:\n")
                print(last_code)
                _save_build_code(last_code, goal_text, explicit_path=explicit_path)
            else:
                print("Gemini did not return a usable solution.")
        except Exception as e:
            print(f"Expert fallback error: {e}")


def cmd_run(code: str = None):
    """Execute code in sandbox. If no code provided, use last generated code."""
    global last_code
    to_run = code if code else last_code
    if not to_run:
        print("No code to run. Use /build first or provide code: /run 'print(1+1)'")
        return

    # If code looks like a shell command and dangerous, ask permission
    if is_dangerous(to_run):
        allowed = ask_permission(to_run)
        if not allowed:
            print("Command not allowed by user.")
            return

    with get_sandbox() as sb:
        print("📦 Running in sandbox...")
        # Assume Python code by default
        stdout, stderr, rc = sb.run_python(to_run)
        print("--- stdout ---")
        print(stdout if stdout else "(no output)")
        if stderr:
            print("--- stderr ---")
            print(stderr)
        print(f"--- exit code: {rc} ---")


def cmd_sandbox_status():
    sb = get_sandbox()
    print(f"Sandbox limits: timeout={sb.timeout_sec}s, memory={sb.max_memory_mb}MB, disk={sb.max_disk_mb}MB")
    print("Dangerous command detection enabled.")


def cmd_constitution():
    print("=== Project Constitution ===")
    print(constitution)


def cmd_update_constitution():
    print("Editing constitution. Enter new content (end with Ctrl+D / Ctrl+Z on new line):")
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    new_content = "\n".join(lines)
    try:
        project_memory.update_constitution(new_content)
        global constitution
        constitution = new_content
        print("Constitution updated.")
    except Exception as e:
        print(f"Failed to update constitution: {e}")


def cmd_search(pattern: str):
    if not pattern:
        print("Usage: /search <pattern>")
        return
    print(f"Searching for '{pattern}'...")
    results = grep(pattern, max_count=20)
    if not results:
        print("No matches found.")
        return
    for line in results[:15]:
        print(line)
    if len(results) > 15:
        print(f"... and {len(results) - 15} more.")


def cmd_read(filepath: str, lines: str = ""):
    if not filepath:
        print("Usage: /read <filepath> [start-end]")
        return
    start = 1
    end = None
    if lines:
        parts = lines.split("-")
        if len(parts) == 2:
            try:
                start = int(parts[0])
                end = int(parts[1])
            except ValueError:
                pass
    content = read_file(filepath, start, end)
    print(content)
    if len(content) > 2000:
        print("\n... (output truncated, use /read with line range)")


def cmd_glob(pattern: str):
    if not pattern:
        print("Usage: /glob <pattern>")
        return
    paths = glob_files(pattern)
    if not paths:
        print("No files matched.")
        return
    for p in paths[:20]:
        print(p)
    if len(paths) > 20:
        print(f"... and {len(paths) - 20} more.")


def cmd_backend(name: str, auth_method: str = None, api_key: str = None, oauth_creds_path: str = None, persist: bool = False, ask_save: bool = True):
    """Switch LLM backend at runtime."""
    name = name.strip()
    valid = ("shimmy", "gemini-apikey", "gemini-oauth", "gemini-flash", "gemini-pro", "openai")
    if name not in valid:
        print("Invalid backend. Choose: shimmy, gemini-apikey, openai, gemini-oauth, gemini-flash, gemini-pro")
        return
    global llm_client, orchestrator, tot, config
    llm_cfg = config.setdefault("llm", {})
    gem_cfg = llm_cfg.setdefault("gemini", {})
    llm_cfg["backend"] = name
    if auth_method:
        gem_cfg["auth_method"] = auth_method
    if api_key is not None:
        gem_cfg["api_key"] = api_key
    if oauth_creds_path is not None:
        gem_cfg["oauth_creds_path"] = oauth_creds_path
    if name == "gemini-apikey":
        gem_cfg["auth_method"] = "apikey"
    if name == "gemini-oauth":
        gem_cfg["auth_method"] = "oauth"
    if name == "shimmy":
        from core.shimmy_manager import ensure_shimmy_running

        try:
            ensure_shimmy_running(dict(llm_cfg.get("shimmy", {})))
        except Exception as exc:
            print(f"Warning: could not start Shimmy: {exc}")
    # attempt to create new client
    try:
        new_client = get_llm_client(llm_cfg)
    except Exception as e:
        print(f"Failed to initialize backend {name}: {e}")
        fallback = (llm_cfg.get("fallback") or "").strip()
        if not fallback or fallback == name:
            return
        print(f"Falling back to {fallback}")
        llm_cfg["backend"] = fallback
        try:
            new_client = get_llm_client(llm_cfg)
        except Exception as e2:
            print(f"Fallback failed: {e2}")
            return
    llm_client = new_client
    tot = TreeOfThoughts(llm_client, max_depth=3, width=3, eval_threshold=0.4)
    orchestrator = Orchestrator(llm_client)
    print(f"Switched backend to: {name}")
    if persist:
        try:
            with open(CONFIG_PATH, "r") as f:
                full = yaml.safe_load(f) or {}
            full.setdefault("llm", {})
            full["llm"]["backend"] = llm_cfg.get("backend")
            full["llm"]["fallback"] = llm_cfg.get("fallback", "")
            full.setdefault("llm", {}).setdefault("gemini", {})
            full["llm"]["gemini"].update(gem_cfg)
            full.setdefault("llm", {}).setdefault("shimmy", {})
            full["llm"]["shimmy"].update(llm_cfg.get("shimmy", {}))
            with open(CONFIG_PATH, "w") as f:
                yaml.safe_dump(full, f)
            print("Config updated.")
        except Exception as e:
            print(f"Failed to write config: {e}")
    elif ask_save:
        save = input("Save this backend to virtuoso.yaml? (y/N): ").strip().lower()
        if save == "y":
            try:
                with open(CONFIG_PATH, "r") as f:
                    full = yaml.safe_load(f) or {}
                full.setdefault("llm", {})
                full["llm"]["backend"] = llm_cfg.get("backend")
                full["llm"]["fallback"] = llm_cfg.get("fallback", "")
                full.setdefault("llm", {}).setdefault("gemini", {})
                full["llm"]["gemini"].update(gem_cfg)
                full.setdefault("llm", {}).setdefault("shimmy", {})
                full["llm"]["shimmy"].update(llm_cfg.get("shimmy", {}))
                with open(CONFIG_PATH, "w") as f:
                    yaml.safe_dump(full, f)
                print("Config updated.")
            except Exception as e:
                print(f"Failed to write config: {e}")


def cmd_status():
    from core.hardware import is_low_memory_machine, system_ram_gb

    llm_cfg = config.get("llm", {})
    backend = llm_cfg.get("backend", "gemini-apikey")
    profile = config.get("cli", {}).get("active_profile", "cloud")
    print(f"Profile: {profile}")
    print(f"LLM backend: {backend}")
    ram = system_ram_gb()
    if ram is not None:
        print(f"System RAM: {ram:.1f} GB")
    if is_low_memory_machine() and backend != "gemini-apikey" and not backend.startswith("gemini"):
        print("Tip: on 8GB laptops use /profile cloud and /gemini setup (Shimmy is slow on integrated GPU).")
    gem_cfg = llm_cfg.get("gemini", {})
    if backend.startswith("gemini"):
        auth_method = gem_cfg.get("auth_method", "apikey")
        print(f"Gemini auth method: {auth_method}")
        gem_key = gem_cfg.get("api_key") or os.environ.get("GEMINI_API_KEY")
        print(f"Gemini API key: {'present' if gem_key else 'absent'}")
        print(f"Gemini OAuth path: {gem_cfg.get('oauth_creds_path', '~/.gemini/oauth_creds.json')}")
        print(f"Gemini model: {gem_cfg.get('model', gem_cfg.get('model_flash', DEFAULT_GEMINI_FLASH))}")
    else:
        print("Gemini API key: N/A")
    # Show Shimmy config if present
    shim_cfg = llm_cfg.get("shimmy", {})
    if backend == "shimmy" or shim_cfg.get("enabled", False):
        port = shim_cfg.get("port", 8080)
        binary_path = shim_cfg.get("binary_path") or "PATH or ./bin"
        print("Shimmy backend:")
        print(f"  enabled: {shim_cfg.get('enabled', True)}")
        print(f"  port: {port}")
        print(f"  binary_path: {binary_path}")
        model_path = shim_cfg.get("model_path") or "(auto)"
        print(f"  model_path: {model_path}")
        print(f"  running: {is_shimmy_running(port)}")
    if backend != "shimmy" and shim_cfg.get("enabled", True):
        print("Local Shimmy: available via /backend shimmy")
    print(f"Tools: ripgrep={'available' if has_ripgrep() else 'fallback'}")
    print(f"Conversation turns: {len(conversation_history)//2}")
    print(f"History length: {len(history)//2} exchanges")
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem_mb = proc.memory_info().rss / 1024 / 1024
        print(f"Virtuoso memory: {mem_mb:.1f} MB")
    except ImportError:
        print("Install psutil for memory stats (optional)")


def cmd_shimmy_status():
    llm_cfg = config.get("llm", {})
    shim_cfg = llm_cfg.get("shimmy", {})
    port = shim_cfg.get("port", 8080)
    binary_path = shim_cfg.get("binary_path") or "PATH or ./bin"
    print("Shimmy status:")
    print(f"  enabled: {shim_cfg.get('enabled', True)}")
    print(f"  port: {port}")
    print(f"  binary_path: {binary_path}")
    print(f"  model_path: {shim_cfg.get('model_path') or '(auto)'}")
    print(f"  server running: {is_shimmy_running(port)}")


def cmd_shimmy_start():
    llm_cfg = config.get("llm", {})
    shim_cfg = dict(llm_cfg.get("shimmy", {}))
    try:
        start_shimmy(
            port=shim_cfg.get("port", 8080),
            model=shim_cfg.get("model", "auto"),
            binary_path=shim_cfg.get("binary_path"),
            config=shim_cfg,
        )
        port = shim_cfg.get("port", 8080)
        model = resolve_shimmy_model(
            port=port,
            configured=shim_cfg.get("model", "auto"),
            preferred_path=shim_cfg.get("model_path"),
        )
        print(f"Shimmy started on port {port} (model: {model})")
    except Exception as e:
        print(f"Failed to start Shimmy: {e}")


def cmd_shimmy_stop():
    from core.shimmy_manager import stop_shimmy_quiet

    try:
        stop_shimmy()
        print("Shimmy stopped.")
    except Exception:
        stop_shimmy_quiet()
        print("Shimmy is not running (or was started outside this session).")


def cmd_openai(args: str = ""):
    """OpenAI-compatible setup: /openai setup | /openai openrouter | /openai groq | /openai status"""
    global config
    args = args.strip().lower()
    if not args or args == "status":
        oai = config.get("llm", {}).get("openai", {})
        from core.openai_compat_client import resolve_openai_api_key

        key = resolve_openai_api_key(oai)
        print("OpenAI-compatible API status:")
        print(f"  backend: {config.get('llm', {}).get('backend', '')}")
        print(f"  base_url: {oai.get('base_url', 'https://api.openai.com/v1')}")
        print(f"  model: {oai.get('model', 'gpt-4o-mini')}")
        print(f"  api_key: {mask_api_key(key or '')}")
        print("  providers: openai, openrouter, groq, together")
        print("  setup: /openai setup   or   /openai openrouter")
        return

    if args == "setup":
        print("Providers: openai, openrouter, groq, together")
        provider = input("Provider [openrouter]: ").strip().lower() or "openrouter"
        preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["openrouter"])
        print(f"Get a key at: {preset['key_url']}")
        key = input("Paste API key: ").strip()
        if not key:
            print("Cancelled.")
            return
        try:
            apply_provider_preset(provider, key)
            _reconnect_llm()
            print(f"Connected via {provider} (model: {preset['model']}). Run /backend openai if needed.")
        except Exception as exc:
            print(f"Setup failed: {exc}")
        return

    if args in PROVIDER_PRESETS:
        preset = PROVIDER_PRESETS[args]
        print(f"Get a key at: {preset['key_url']}")
        key = input("Paste API key: ").strip()
        if not key:
            print("Cancelled.")
            return
        try:
            apply_provider_preset(args, key)
            _reconnect_llm()
            print(f"Connected via {args} (model: {preset['model']}).")
        except Exception as exc:
            print(f"Setup failed: {exc}")
        return

    print("Usage: /openai setup | /openai openrouter | /openai groq | /openai together | /openai status")


def cmd_gemini(args: str = ""):
    """Gemini API key setup: /gemini setup | /gemini status | /gemini <api_key>"""
    global llm_client, config
    args = args.strip()
    if not args or args == "status":
        key = get_gemini_api_key(config)
        backend = config.get("llm", {}).get("backend", "")
        model = config.get("llm", {}).get("gemini", {}).get("model", DEFAULT_GEMINI_FLASH)
        print("Gemini status:")
        print(f"  backend: {backend}")
        print(f"  model: {model}")
        print(f"  api_key: {mask_api_key(key or '')}")
        print(f"  configured: {'yes' if key else 'no'}")
        if not key:
            print(f"  setup: /gemini setup  (get a key at {GEMINI_KEY_URL})")
        return

    if args == "setup":
        key = prompt_for_api_key()
        if not key:
            print("Gemini setup cancelled.")
            return
        try:
            save_gemini_api_key(key)
            config = load_config()
            llm_cfg = config.get("llm", {})
            llm_client = get_llm_client(llm_cfg)
            print(f"Gemini connected (model: {llm_cfg.get('gemini', {}).get('model', DEFAULT_GEMINI_FLASH)}).")
            print("Type your prompt directly at > — no /generate needed.")
        except Exception as exc:
            print(f"Gemini setup failed: {exc}")
        return

    # Treat remainder as raw API key
    try:
        save_gemini_api_key(args)
        config = load_config()
        llm_cfg = config.get("llm", {})
        llm_client = get_llm_client(llm_cfg)
        print(f"Gemini API key saved ({mask_api_key(args)}). Backend switched to gemini-apikey.")
    except Exception as exc:
        print(f"Failed to save Gemini API key: {exc}")


def cmd_shimmy_install():
    try:
        from core.model_manager import ensure_default_model

        shim_path = install_shimmy()
        print(f"Shimmy installed at: {shim_path}")
        model_path = ensure_default_model()
        print(f"Default model installed at: {model_path}")
        print("Run /shimmy start to launch the local server.")
    except Exception as exc:
        print(f"Automatic install failed: {exc}")
        print(install_shimmy_help())


def cmd_profile(name: str = ""):
    if not name or name == "list":
        print("Profiles:", ", ".join(list_profiles()))
        print("Usage: /profile cloud | local | offline")
        return
    try:
        apply_profile(name, persist=True)
        global config, llm_client
        config = load_config()
        llm_cfg = config.get("llm", {})
        llm_client = get_llm_client(llm_cfg)
        print(f"Profile '{name}' applied and saved. Backend: {llm_cfg.get('backend')}")
        if name == "local":
            print("Run /shimmy start if the local server is not already running.")
    except Exception as exc:
        print(f"Profile error: {exc}")


def cmd_serve(host: str = "127.0.0.1", port: int = 8765):
    from core.ide_server import run_ide_server

    print("Starting IDE-compatible API server (Ctrl+C to stop)...")
    run_ide_server(host=host, port=port)


def cmd_dashboard(host: str = "127.0.0.1", port: int = 8788, open_browser: bool = True):
    from core.web_dashboard import run_dashboard

    run_dashboard(host=host, port=port, open_browser=open_browser)


def cmd_config():
    print("Current config (read-only preview):")
    for section, values in config.items():
        print(f"{section}:")
        if isinstance(values, dict):
            for k, v in values.items():
                print(f"  {k}: {v}")
        else:
            print(f"  {values}")


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def cmd_doctor() -> int:
    """Run local readiness checks without calling model providers."""
    from core.paths import config_path
    from core.web_dashboard import _dashboard_html_path, _logo_path

    checks = []

    def add(name: str, ok: bool, detail: str = "", required: bool = False):
        checks.append((name, ok, detail, required))

    add("Python version", sys.version_info >= (3, 10), sys.version.split()[0], required=True)

    try:
        cfg = load_config()
        cfg_path = config_path()
        add("Config file", cfg_path.exists(), str(cfg_path), required=True)
    except Exception as exc:
        cfg = {}
        add("Config file", False, str(exc), required=True)

    llm_cfg = cfg.get("llm", {}) if isinstance(cfg, dict) else {}
    backend = llm_cfg.get("backend", "gemini-apikey")
    gemini_key = bool((llm_cfg.get("gemini", {}).get("api_key") or os.environ.get("GEMINI_API_KEY") or "").strip())
    openai_key = False
    try:
        from core.openai_compat_client import resolve_openai_api_key

        openai_key = resolve_openai_api_key(llm_cfg.get("openai", {})) is not None
    except Exception:
        openai_key = False

    if backend.startswith("gemini"):
        add("Gemini key", gemini_key, "present" if gemini_key else "missing; run /gemini setup")
    elif backend == "openai":
        add("OpenAI-compatible key", openai_key, "present" if openai_key else "missing; run /openai setup")
    else:
        add("Cloud API key", True, "not required for current backend")

    add("Dashboard HTML", _dashboard_html_path() is not None, str(_dashboard_html_path() or "missing"), required=True)
    add("Icon asset", _logo_path() is not None, str(_logo_path() or "missing"))
    add("ripgrep", has_ripgrep(), shutil.which("rg") or "optional fallback will be used")
    add("Dashboard port", _port_available("127.0.0.1", int(cfg.get("cli", {}).get("dashboard_port", 8788))), "127.0.0.1:8788")
    add("IDE server port", _port_available("127.0.0.1", int(cfg.get("cli", {}).get("ide_server_port", 8765))), "127.0.0.1:8765")

    shim_cfg = llm_cfg.get("shimmy", {})
    shimmy_binary = shim_cfg.get("binary_path") or shutil.which("shimmy")
    add("Shimmy binary", bool(shimmy_binary), shimmy_binary or "optional; needed only for /profile local")

    print(f"Virtuoso doctor v{__version__}")
    failed_required = 0
    for name, ok, detail, required in checks:
        marker = "OK" if ok else "WARN"
        if required and not ok:
            failed_required += 1
        print(f"[{marker}] {name}: {detail}")

    if failed_required:
        print(f"\nDoctor found {failed_required} required issue(s).")
        return 1
    warnings = sum(1 for _, ok, _, _ in checks if not ok)
    if warnings:
        print(f"\nDoctor finished with {warnings} warning(s). Cloud API keys and Shimmy are optional depending on your workflow.")
        return 0
    print("\nDoctor finished cleanly.")
    return 0


def run_tui():
    if not init():
        raise RuntimeError("Backend not connected")
    from virtuoso_tui import VirtuosoTUI

    VirtuosoTUI().run()


def main():
    run_onboarding_wizard()
    init()
    print("Virtuoso CLI Agent ready.")
    print("Type a prompt directly (chat mode) or use /plan, /build, /gemini setup, /status, /exit.")
    print("Prefer a UI? Run: python virtuoso.py --dashboard   (opens in your browser)")
    backend = config.get("llm", {}).get("backend", "gemini-apikey")
    if backend.startswith("gemini") and not has_gemini_api_key(config):
        print(f"Run /gemini setup first (free key: {GEMINI_KEY_URL})")
    elif backend == "gemini-apikey" and has_gemini_api_key(config):
        print("Using Google Gemini. Switch to local model: /backend shimmy")
    elif backend == "shimmy":
        print("Using local Shimmy. Switch to Gemini: /backend gemini-apikey")
    print(f"Presets: {list_presets()}")
    print("Commands: /dashboard, /profile cloud|local, /serve, /gemini setup, /openai setup, /plan, /build, /save, /status, /exit")
    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue
            if user_input == "/exit":
                logger.info("Shutting down")
                break
            elif user_input.startswith("/generate "):
                cmd_generate(user_input[10:].strip())
            elif user_input.startswith("/plan "):
                cmd_plan(user_input[6:].strip())
            elif user_input.startswith("/build "):
                cmd_build(user_input[7:].strip())
            elif user_input.startswith("/save "):
                cmd_save(user_input[6:].strip())
            elif user_input == "/save":
                cmd_save()
            elif user_input.startswith("/search "):
                cmd_search(user_input[8:].strip())
            elif user_input.startswith("/run "):
                cmd_run(user_input[5:].strip())
            elif user_input == "/run":
                cmd_run()
            elif user_input == "/sandbox":
                cmd_sandbox_status()
            elif user_input == "/constitution":
                cmd_constitution()
            elif user_input == "/update-constitution":
                cmd_update_constitution()
            elif user_input.startswith("/read "):
                parts = user_input[6:].strip().split(maxsplit=1)
                path = parts[0] if parts else ""
                range_spec = parts[1] if len(parts) > 1 else ""
                cmd_read(path, range_spec)
            elif user_input.startswith("/glob "):
                cmd_glob(user_input[6:].strip())
            elif user_input == "/status":
                cmd_status()
            elif user_input == "/config":
                cmd_config()
            elif user_input == "/clear":
                cmd_clear()
            elif user_input == "/shimmy status":
                cmd_shimmy_status()
            elif user_input == "/shimmy start":
                cmd_shimmy_start()
            elif user_input == "/shimmy stop":
                cmd_shimmy_stop()
            elif user_input == "/shimmy install":
                cmd_shimmy_install()
            elif user_input.startswith("/backend "):
                cmd_backend(user_input[9:].strip())
            elif user_input == "/gemini" or user_input.startswith("/gemini "):
                cmd_gemini(user_input[7:].strip() if user_input.startswith("/gemini ") else "")
            elif user_input == "/openai" or user_input.startswith("/openai "):
                cmd_openai(user_input[8:].strip() if user_input.startswith("/openai ") else "")
            elif user_input == "/serve":
                cmd_serve()
            elif user_input == "/dashboard":
                cmd_dashboard()
            elif user_input.startswith("/profile"):
                cmd_profile(user_input[8:].strip())
            elif user_input.startswith("/fix "):
                cmd_generate(user_input[5:].strip(), preset="fix")
            elif user_input.startswith("/explain "):
                cmd_generate(user_input[9:].strip(), preset="explain")
            elif user_input.startswith("/test "):
                cmd_generate(user_input[6:].strip(), preset="test")
            elif user_input.startswith("/refactor "):
                cmd_generate(user_input[10:].strip(), preset="refactor")
            elif user_input.startswith("/review "):
                cmd_generate(user_input[8:].strip(), preset="review")
            elif not user_input.startswith("/"):
                cmd_generate(user_input)
            else:
                print("Unknown command. Type your prompt directly, or try /plan, /build, /status, /backend gemini-apikey, /exit")
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print(f"Error: {e}")


def parse_args():
    parser = argparse.ArgumentParser(description="Virtuoso CLI Agent")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument("--doctor", action="store_true", help="Check local setup without calling model providers")
    parser.add_argument("--tui", action="store_true", help="Launch the Textual dashboard")
    parser.add_argument("--serve", action="store_true", help="OpenAI-compatible IDE API server")
    parser.add_argument("--serve-host", default="127.0.0.1", help="IDE server bind host")
    parser.add_argument("--serve-port", type=int, default=8765, help="IDE server port")
    parser.add_argument("--dashboard", action="store_true", help="Open browser dashboard UI")
    parser.add_argument("--dashboard-host", default="127.0.0.1", help="Dashboard bind host")
    parser.add_argument("--dashboard-port", type=int, default=8788, help="Dashboard port")
    return parser.parse_args()


def cli_main():
    args = parse_args()
    if args.version:
        print(f"virtuoso {__version__}")
    elif args.doctor:
        raise SystemExit(cmd_doctor())
    elif args.serve:
        cmd_serve(host=args.serve_host, port=args.serve_port)
    elif args.dashboard:
        cmd_dashboard(host=args.dashboard_host, port=args.dashboard_port)
    elif args.tui:
        run_tui()
    else:
        main()


if __name__ == "__main__":
    cli_main()
