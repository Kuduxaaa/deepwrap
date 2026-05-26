from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time

from pathlib import Path
from typing import Optional

from deepwrap.utils.config_store import AppConfig as CLIConfig
from deepwrap.utils.config_store import ConfigStore

try:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.rule import Rule
    from rich.spinner import Spinner
    from rich.text import Text
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency: rich. Install it with: pip install rich"
    ) from exc

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.application import Application
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import Completer, Completion, CompleteEvent
    from prompt_toolkit.document import Document
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency: prompt_toolkit. Install it with: pip install prompt_toolkit"
    ) from exc

from deepwrap import Client
from deepwrap.core import Auth

APP_NAME         = "deepwrap"
TOKEN_ENV_NAME   = "DEEPWRAP_API_KEY"
SUPPORTED_MODELS = ("expert", "default", "vision")
COMMANDS         = (
    "/help",
    "/exit",
    "/quit",
    "/clear",
    "/new",
    "/model",
    "/token",
    "/thinking",
    "/search",
    "/god",
    "/save",
    "/status",
)

HELP_ITEMS = [
    ("/help",            "Show this help"),
    ("/exit",            "Exit the CLI"),
    ("/clear",           "Clear the terminal"),
    ("/new",             "Start a fresh chat session"),
    ("/model <name>",    "Switch model (expert, default, vision)"),
    ("/token",           "Set token interactively"),
    ('/token "<token>"', "Set token inline"),
    ("/thinking on|off", "Show or hide <think> blocks in UI"),
    ("/search on|off",   "Enable or disable search"),
    ("/god on|off",      "Enable or disable God Mode"),
    ("/save",            "Save current settings to config"),
    ("/status",          "Show current session status"),
]



class SlashCommandCompleter(Completer):
    """
    Autocomplete slash commands only when the input starts with a slash.
    """

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        text = document.text_before_cursor

        if not text.startswith("/"):
            return

        for command in COMMANDS:
            if command.startswith(text):
                yield Completion(
                    command,
                    start_position = -len(text),
                    display         = command,
                )


class DeepWrapCLI:
    """
    Interactive terminal UI for DeepWrap.
    """

    def __init__(self) -> None:
        self.console = Console(highlight = False)
        self.store   = ConfigStore()
        self.config  = self.store.load()

        env_token = os.getenv(TOKEN_ENV_NAME) or os.getenv("DEEPSEEK_API_KEY")
        if env_token:
            self.config.token = env_token

        history_path = self.store.path.parent / "history.txt"

        self.prompt = PromptSession(
            history               = FileHistory(str(history_path)),
            auto_suggest          = AutoSuggestFromHistory(),
            completer             = SlashCommandCompleter(),
            complete_while_typing = True,
        )

        self.client: Optional[Client] = None
        self.chat                     = None
        self._last_ctrl_c_at          = 0.0

        if self.config.token:
            self._boot_client()

    def _erase_last_input_line(self) -> None:
        """
        Remove the last prompt line from the terminal.

        This is used to avoid showing the raw prompt-toolkit input line and the
        styled user bubble at the same time.

        The sequence is intentionally conservative because moving the cursor
        around near the terminal bottom edge is fragile on some terminals.
        """

        try:
            stream = self.console.file

            if hasattr(stream, "isatty") and not stream.isatty():
                return

            stream.write("\r")
            stream.write("\x1b[2K")
            stream.write("\x1b[1A")
            stream.write("\x1b[2K")
            stream.write("\r")
            stream.flush()
        except Exception:
            pass

    def run(self) -> None:
        """
        Run the interactive CLI loop.
        """

        self._clear_screen()
        self._render_header()
        self._render_intro()

        if not self.config.token:
            self._print_system(
                "No token configured.",
                style = "yellow",
            )
            self._offer_token_setup()

        while True:
            try:
                user_input = self.prompt.prompt(
                    self._prompt_text(),
                )

                self._erase_last_input_line()
                self._last_ctrl_c_at = 0.0

            except KeyboardInterrupt:
                now = time.monotonic()

                if now - self._last_ctrl_c_at <= 1.2:
                    self.console.print()
                    self._print_system("Bye.", style = "dim")
                    return

                self._last_ctrl_c_at = now
                self.console.print()
                self._print_system(
                    "Input cancelled. Press Ctrl+C again to exit.",
                    style = "yellow",
                )
                continue

            except EOFError:
                self.console.print()
                self._print_system("Bye.", style = "dim")
                return

            message = user_input.strip()
            if not message:
                continue

            if message.startswith("/"):
                if not self._handle_command(message):
                    return
                continue

            if not self._ensure_chat():
                continue

            self._render_user(message)
            self._stream_assistant(message)

    def _handle_command(self, raw: str) -> bool:
        """
        Handle slash commands.

        Returns:
            False if the CLI should exit, otherwise True.
        """

        try:
            parts = shlex.split(raw)
        except ValueError as exc:
            self._print_system(f"Command parse error: {exc}", style = "red")
            return True

        command = parts[0].lower()
        args    = parts[1:]

        if command in {"/exit", "/quit"}:
            return False

        if command == "/help":
            self._render_help()
            return True

        if command == "/clear":
            self._clear_screen()
            self._render_header()
            self._render_intro()
            return True

        if command == "/new":
            self._create_chat()
            self._print_system("Started a new chat session.", style = "green")
            return True

        if command == "/status":
            self._render_status()
            return True

        if command == "/save":
            self.store.save(self.config)
            self._print_system(f"Saved config to {self.store.path}", style = "green")
            return True

        if command == "/model":
            if not args:
                self._print_system(
                    f"Current model: {self.config.model}",
                    style = "cyan",
                )
                return True

            model = args[0].strip().lower()

            if model not in SUPPORTED_MODELS:
                self._print_system(
                    f"Unsupported model: {model}. Supported: {', '.join(SUPPORTED_MODELS)}",
                    style = "red",
                )
                return True

            self.config.model = model
            self._create_chat()
            self._print_system(f"Model switched to {model}.", style = "green")
            return True

        if command == "/thinking":
            if not args:
                state = "on" if self.config.show_thinking else "off"
                self._print_system(f"Thinking display is {state}.", style = "cyan")
                return True

            value = args[0].strip().lower()

            if value not in {"on", "off"}:
                self._print_system("Usage: /thinking on|off", style = "red")
                return True

            self.config.show_thinking = value == "on"
            state = "enabled" if self.config.show_thinking else "hidden"
            self._print_system(f"Thinking blocks are now {state}.", style = "green")
            return True

        if command == "/search":
            if not args:
                state = "on" if self.config.search_enabled else "off"
                self._print_system(f"Search is {state}.", style = "cyan")
                return True

            value = args[0].strip().lower()

            if value not in {"on", "off"}:
                self._print_system("Usage: /search on|off", style = "red")
                return True

            self.config.search_enabled = value == "on"
            state = "enabled" if self.config.search_enabled else "disabled"
            self._print_system(f"Search is now {state}.", style = "green")
            return True

        if command == "/god":
            if not args:
                state = "on" if self.config.god_mode else "off"
                self._print_system(f"God Mode is {state}.", style = "cyan")
                return True

            value = args[0].strip().lower()

            if value not in {"on", "off"}:
                self._print_system("Usage: /god on|off", style = "red")
                return True

            self.config.god_mode = value == "on"
            self._create_chat()
            state = "enabled" if self.config.god_mode else "disabled"
            self._print_system(f"God Mode is now {state}.", style = "green")
            return True

        if command == "/token":
            inline_token = args[0] if args else None
            self._set_token_interactive(inline_token)
            return True

        self._print_system(f"Unknown command: {command}", style = "red")
        return True

    def _offer_token_setup(self) -> None:
        """
        Offer a modern auth method picker when no token is configured.
        """

        choice = self._select_auth_method()

        if choice == "browser":
            self._run_browser_auth()
            return

        if choice == "manual":
            self._set_token_interactive()
            return

        self._print_system(
            "Token setup skipped. You can run /token later.",
            style = "yellow",
        )

    def _select_auth_method(self) -> Optional[str]:
        """
        Show a modern arrow-key auth selector.

        Returns:
            "browser", "manual", or None.
        """

        options = [
            (
                "browser",
                "Login via browser  (Auto)",
                "Open the browser and let Client.auth.browser() handle auth.",
            ),
            (
                "manual",
                "Use Bearer         (Manual)",
                "Paste a bearer token with a cleaner prompt.",
            ),
        ]

        selected = {"index": 0}

        def get_fragments():
            fragments = [
                ("fg:#60a5fa bold", " DeepWrap setup\n"),
                ("fg:#94a3b8", " Choose an auth method\n\n"),
            ]

            for index, (_, label, description) in enumerate(options):
                active = index == selected["index"]

                if active:
                    fragments.extend(
                        [
                            ("bg:#172554 fg:#ffffff bold", "  ● "),
                            ("bg:#172554 fg:#bfdbfe bold", f"{label}"),
                            ("", "\n"),
                            ("fg:#93c5fd", f"     {description}\n\n"),
                        ]
                    )
                else:
                    fragments.extend(
                        [
                            ("fg:#475569", "  ○ "),
                            ("fg:#94a3b8", f"{label}"),
                            ("", "\n"),
                            ("fg:#64748b", f"     {description}\n\n"),
                        ]
                    )

            fragments.append(
                ("fg:#64748b", " ↑/↓ or Tab to move • Enter to confirm • Esc to cancel ")
            )

            return fragments

        kb = KeyBindings()

        @kb.add("up")
        def _(event):
            selected["index"] = (selected["index"] - 1) % len(options)

        @kb.add("down")
        @kb.add("tab")
        def _(event):
            selected["index"] = (selected["index"] + 1) % len(options)

        @kb.add("s-tab")
        def _(event):
            selected["index"] = (selected["index"] - 1) % len(options)

        @kb.add("enter")
        def _(event):
            event.app.exit(result = options[selected["index"]][0])

        @kb.add("escape")
        @kb.add("c-c")
        def _(event):
            event.app.exit(result = None)

        style = Style.from_dict(
            {
                "dialog": "bg:#020617",
            }
        )

        body = Window(
            content            = FormattedTextControl(get_fragments),
            always_hide_cursor = True,
        )

        app = Application(
            layout        = Layout(body),
            key_bindings  = kb,
            full_screen   = False,
            mouse_support = False,
            style         = style,
        )

        self.console.print()
        result = app.run()
        self.console.print()

        return result

    def _run_browser_auth(self) -> None:
        """
        Start browser-based auth via the client's auth API.

        This assumes your Client supports being instantiated without a token
        and exposes `client.auth.browser()`.
        """

        self._clear_screen()
        self._render_header()
        self._render_intro()
        
        self._print_system(
            "Starting browser auth...",
            style = "cyan",
        )

        try:
            result = Auth().browser()

            if result is None:
                self._print_system("Browser auth was cancelled or failed.", style = "red")
                return

        except KeyboardInterrupt:
            self._print_system("Browser auth cancelled.", style = "yellow")
            return
        
        except Exception as exc:
            self._print_system(f"Browser auth failed: {exc}", style = "red")
            self._offer_token_setup()
            return

        token = self._extract_token_from_auth_result(result)

        if not token or token is None or len(token.strip()) == 0:
            self._print_system(
                "Browser auth did not return a token.",
                style = "red",
            )
            
            self._offer_token_setup()
            return

        self.config.token = token
        self._boot_client(reset_chat = True)
        self._print_system("Browser auth completed.", style = "green")

        save_local = self._ask_yes_no(
            "Save token to DeepWrap config file?",
            default = True,
        )

        if save_local:
            self.store.save(self.config)
            self._print_system(f"Saved token to {self.store.path}", style = "green")

    @staticmethod
    def _extract_token_from_auth_result(result) -> Optional[str]:
        """
        Normalize the return value of `client.auth.browser()` into a token.
        """

        if isinstance(result, str):
            return result.strip() or None

        if isinstance(result, dict):
            for key in ("token", "api_key", "bearer_token", "access_token"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        for attr in ("token", "api_key", "bearer_token", "access_token"):
            value = getattr(result, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()

        return None

    def _set_token_interactive(self, token: Optional[str] = None) -> None:
        """
        Set the API token and optionally persist it.
        """

        if not token:
            self.console.print()
            self.console.print(Text("manual auth", style = "bold #60a5fa"))
            self.console.print(
                Text(
                    "Paste your bearer token below. It will not be echoed.",
                    style = "#93c5fd",
                )
            )
            token = self.prompt.prompt(
                [("#60a5fa bold", " token "), ("#93c5fd", "> ")],
                is_password = True,
            ).strip()
            self.console.print()

        if not token:
            self._print_system("Token was empty. Nothing changed.", style = "yellow")
            return

        self.config.token = token
        try:
            self._boot_client(reset_chat = True)
        except Exception as exc:
            self._print_system(f"Failed to boot client: {exc}", style = "red")
            self._select_auth_method()
            return
        
        self._print_system("Token updated for current session.", style = "green")

        save_local = self._ask_yes_no(
            "Save token to DeepWrap config file?",
            default = True,
        )

        if save_local:
            self.store.save(self.config)
            self._print_system(f"Saved token to {self.store.path}", style = "green")

        save_system = self._ask_yes_no(
            f"Persist token to system environment variable {TOKEN_ENV_NAME}?",
            default = False,
        )

        if save_system:
            ok, message = self._persist_system_env(TOKEN_ENV_NAME, token)
            self._print_system(message, style = "green" if ok else "yellow")

    def _persist_system_env(self, key: str, value: str) -> tuple[bool, str]:
        """
        Persist a token as a user-level environment variable.
        """

        try:
            if os.name == "nt":
                subprocess.run(
                    ["setx", key, value],
                    check          = True,
                    capture_output = True,
                    text           = True,
                )
                return True, f"Saved {key} with setx. Restart your terminal to load it."

            profile = Path.home() / ".profile"
            line    = f'export {key}="{value}"\n'

            if profile.exists():
                existing = profile.read_text(encoding = "utf-8")
                updated  = re.sub(
                    rf'^export\s+{re.escape(key)}=.*$\n?',
                    '',
                    existing,
                    flags = re.MULTILINE,
                )
            else:
                updated = ""

            updated += ("\n" if updated and not updated.endswith("\n") else "") + line
            profile.write_text(updated, encoding = "utf-8")

            return True, f"Saved {key} to {profile}. Restart your shell to load it."

        except Exception as exc:  # pragma: no cover
            return False, f"Could not persist system env token: {exc}"

    def _stream_assistant(self, prompt: str) -> None:
        """
        Render assistant output live with markdown formatting.

        The live region is intentionally cropped near the terminal bottom edge
        to avoid crashes or cursor corruption in small terminals. After the
        streaming finishes, the final full content is printed statically.
        """

        thinking = ""
        answer   = ""
        phase    = "thinking"

        with Live(
            self._build_live_renderable(thinking, answer, phase),
            console            = self.console,
            refresh_per_second = 18,
            transient          = True,
            vertical_overflow  = "ellipsis",
        ) as live:
            try:
                for kind, chunk in self.chat.respond_structured(
                    prompt   = prompt,
                    thinking = True,
                    search   = self.config.search_enabled,
                ):
                    if kind == "think":
                        thinking += chunk

                        if not answer:
                            phase = "thinking"

                    elif kind == "response":
                        answer += chunk
                        phase = "response"

                    live.update(
                        self._build_live_renderable(
                            thinking = thinking,
                            answer   = answer,
                            phase    = phase,
                        )
                    )

            except KeyboardInterrupt:
                live.stop()
                self.console.print()
                self._print_system(
                    "Generation stopped.",
                    style = "yellow",
                )
                return

            except Exception as exc:
                live.update(Text(str(exc), style = "bold red"))
                return

        self._print_assistant_final(thinking, answer)

    def _build_live_renderable(
        self,
        thinking: str,
        answer: str,
        phase: str,
    ):
        """
        Build the temporary live renderable shown while a response is streaming.
        """

        parts = []

        if self.config.show_thinking:
            if phase == "thinking":
                parts.append(
                    Spinner(
                        "dots",
                        text  = " thinking",
                        style = "bold #60a5fa",
                    )
                )

            elif thinking:
                parts.append(Text("thinking", style = "bold #60a5fa"))

            if thinking:
                parts.append(Text(thinking, style = "dim #94a3b8"))

            if thinking or phase == "thinking":
                parts.append(Text(""))

        else:
            if phase == "thinking" and not answer:
                parts.append(
                    Spinner(
                        "dots",
                        text  = " DeepWrap is thinking",
                        style = "bold #60a5fa",
                    )
                )
                parts.append(Text(""))

        if answer:
            parts.append(Text("DeepWrap", style = "bold #3b82f6"))
            parts.append(Markdown(answer))
        else:
            parts.append(Text("DeepWrap", style = "bold #3b82f6"))

        return Group(*parts)

    def _print_assistant_final(self, thinking: str, answer: str) -> None:
        """
        Print the final completed assistant output as normal static content.
        """

        self.console.print()

        if self.config.show_thinking and thinking:
            self.console.print(Text("thinking", style = "bold #60a5fa"))
            self.console.print(Text(thinking, style = "dim #94a3b8"))
            self.console.print()

        self.console.print(Text("DeepWrap", style = "bold #3b82f6"))

        if answer.strip():
            self.console.print(Markdown(answer))
        else:
            self.console.print(Text("(empty response)", style = "dim"))

        self.console.print()

    def _render_header(self) -> None:
        """
        Render the top banner.
        """

        banner = Text()
        banner.append("██████╗ ███████╗███████╗██████╗ ██╗    ██╗██████╗  █████╗ ██████╗ \n", style = "bold #3b82f6")
        banner.append("██╔══██╗██╔════╝██╔════╝██╔══██╗██║    ██║██╔══██╗██╔══██╗██╔══██╗\n", style = "bold #3b82f6")
        banner.append("██║  ██║█████╗  █████╗  ██████╔╝██║ █╗ ██║██████╔╝███████║██████╔╝\n", style = "bold #3b82f6")
        banner.append("██║  ██║██╔══╝  ██╔══╝  ██╔═══╝ ██║███╗██║██╔══██╗██╔══██║██╔═══╝ \n", style = "bold #3b82f6")
        banner.append("██████╔╝███████╗███████╗██║     ╚███╔███╔╝██║  ██║██║  ██║██║     \n", style = "bold #3b82f6")
        banner.append("╚═════╝ ╚══════╝╚══════╝╚═╝      ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ", style = "bold #3b82f6")

        self.console.print()
        self.console.print(banner)
        self.console.print()

        self.console.print(
            Text(
                "Do not pay in API calls for what a bad prompt can sabotage for free.",
                style = "#94a3b8",
            )
        )
        self.console.print(
            Text("Type ", style = "#94a3b8")
            + Text("/help", style = "bold #60a5fa")
            + Text(" for commands.", style = "#94a3b8")
        )
        self.console.print()

    def _render_intro(self) -> None:
        """
        Render current runtime state summary.
        """

        token_state = "set" if self.config.token else "missing"

        self.console.print(Rule(style = "#1e3a8a"))
        self.console.print(
            Text(
                f"model={self.config.model}  |  token={token_state}  |  thinking={'on' if self.config.show_thinking else 'off'}  |  search={'on' if self.config.search_enabled else 'off'}  |  god={'on' if self.config.god_mode else 'off'}",
                style = "#93c5fd",
            )
        )
        self.console.print()

    def _render_help(self) -> None:
        """
        Render command help without borders.
        """

        self.console.print()
        self.console.print(Text("help", style = "bold #60a5fa"))

        for command, description in HELP_ITEMS:
            line = Text()
            line.append("  ")
            line.append(command.ljust(20), style = "bold #bfdbfe")
            line.append(description, style = "#cbd5e1")
            self.console.print(line)

        self.console.print()

    def _render_status(self) -> None:
        """
        Render current runtime status without borders.
        """

        lines = [
            f"model: {self.config.model}",
            f"token: {'set' if self.config.token else 'missing'}",
            f"thinking display: {'on' if self.config.show_thinking else 'off'}",
            f"search: {'on' if self.config.search_enabled else 'off'}",
            f"god mode: {'on' if self.config.god_mode else 'off'}",
            f"chat session: {'active' if self.chat is not None else 'none'}",
            f"config file: {self.store.path}",
        ]

        self.console.print()
        self.console.print(Text("status", style = "bold #60a5fa"))
        self.console.print(Text("\n".join(lines), style = "#dbeafe"))
        self.console.print()

    def _render_user(self, message: str) -> None:
        """
        Render a user message once, with a subtle blue background.
        """

        name = Text(" You ", style = "bold white on #2563eb")
        body = Text(f" {message} ", style = "#dbeafe on #172554")

        self.console.print()
        self.console.print(name, end = " ")
        self.console.print(body)
        self.console.print()

    def _print_system(self, message: str, style: str = "#94a3b8") -> None:
        """
        Render a system/status message.
        """

        self.console.print(Text(message, style = style))

    def _prompt_text(self):
        """
        Return the prompt text shown for user input.
        """

        return [("#3b82f6 bold", "> ")]

    def _boot_client(self, reset_chat: bool = True) -> None:
        """
        Create the root client from the current token.
        """

        if not self.config.token:
            self.client = None
            self.chat   = None
            return

        try:
            self.client = Client(api_key = self.config.token)

            if reset_chat:
                self._create_chat()

        except Exception as exc:
            self._print_system(f"Failed to initialize client: {exc}", style = "red")
            
            if 'invalid token' in str(exc).lower():
                self._clear_screen()
                self._render_header()
                self._render_intro()
                self._print_system("The provided token is invalid. Please set a valid token.", style = "red")
                self._offer_token_setup()

    def _create_chat(self) -> None:
        """
        Create a new chat session using the current model and God Mode setting.
        """

        if self.client is None:
            self.chat = None
            return

        self.chat = self.client.chats.create_session(
            model    = self.config.model,
            god_mode = self.config.god_mode,
        )

    def _ensure_chat(self) -> bool:
        """
        Ensure a chat session exists before sending a prompt.
        """

        if self.client is None:
            self._offer_token_setup()

            if self.client is None:
                self._print_system(
                    "No token configured. Use /token first.",
                    style = "yellow",
                )
                return False

        if self.chat is None:
            self._create_chat()

        return self.chat is not None

    def _ask_yes_no(self, prompt: str, default: bool) -> bool:
        """
        Ask a yes/no question interactively.
        """

        suffix = "[Y/n]" if default else "[y/N]"
        reply  = self.prompt.prompt(f"{prompt} {suffix} ").strip().lower()

        if not reply:
            return default

        return reply in {"y", "yes"}

    def _clear_screen(self) -> None:
        """
        Clear the terminal screen.
        """

        self.console.clear()


def main() -> None:
    """
    CLI entrypoint.
    """

    DeepWrapCLI().run()
