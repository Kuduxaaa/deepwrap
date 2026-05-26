from __future__ import annotations

import sys
from typing import Optional

import click

from deepwrap import Client
from deepwrap.config import PROJECT_VERSION
from deepwrap.core import Auth
from deepwrap.interfaces.cli import main as interactive_main
from deepwrap.utils.bearer_token_extractor import BearerTokenExtractor
from deepwrap.utils.config_store import ConfigStore


APP_NAME = "deepwrap"
SUPPORTED_MODELS = ("expert", "default", "vision")


class DeepWrapCLIError(click.ClickException):
    """
    User-facing CLI error.
    """



def load_saved_token() -> Optional[str]:
    """
    Load token from local DeepWrap config.
    """

    config = ConfigStore().load()

    if not config.token:
        return None

    return BearerTokenExtractor.normalize_token(config.token)


def save_token(token: str) -> None:
    """
    Save token to the local DeepWrap config file.
    """

    store = ConfigStore()
    store.update_token(BearerTokenExtractor.normalize_token(token))


def resolve_token(explicit_token: Optional[str] = None) -> str:
    """
    Resolve token from explicit CLI option or saved config.
    """

    if explicit_token:
        return BearerTokenExtractor.normalize_token(explicit_token)

    token = load_saved_token()

    if token:
        return token

    raise DeepWrapCLIError(
        "No token configured. Run `deepwrap auth` first or pass `--token`."
    )


def echo_success(message: str) -> None:
    click.secho(message, fg="green")


def echo_warning(message: str) -> None:
    click.secho(message, fg="yellow", err=True)


def echo_error(message: str) -> None:
    click.secho(message, fg="red", err=True)


@click.group(
    invoke_without_command=True,
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
)
@click.version_option(version=PROJECT_VERSION, prog_name=APP_NAME)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    DeepWrap command line interface.

    Run without a command to start the interactive terminal UI.
    """

    if ctx.invoked_subcommand is None:
        interactive_main()


@cli.command("auth")
@click.option(
    "--manual",
    is_flag=True,
    help="Enter bearer token manually instead of using browser login.",
)
@click.option(
    "--token",
    type=str,
    default=None,
    help="Save a bearer token directly.",
)
@click.option(
    "--timeout",
    type=int,
    default=None,
    help="Timeout in seconds for browser authentication.",
)
@click.option(
    "--save/--no-save",
    default=True,
    show_default=True,
    help="Save the token to the DeepWrap config file.",
)
@click.option(
    "--show-token",
    is_flag=True,
    help="Print the captured token after authentication.",
)
def auth_command(
    manual: bool,
    token: Optional[str],
    timeout: Optional[int],
    save: bool,
    show_token: bool,
) -> None:
    """
    Authenticate DeepWrap.

    Default behavior:
        deepwrap auth

    This opens browser login and captures the bearer token.

    Manual token:
        deepwrap auth --manual

    Direct token:
        deepwrap auth --token "..."
    """

    try:
        captured_token: Optional[str] = None

        if token:
            captured_token = BearerTokenExtractor.normalize_token(token)

        elif manual:
            entered = click.prompt(
                "Bearer token",
                hide_input=True,
                confirmation_prompt=False,
                type=str,
            )

            captured_token = BearerTokenExtractor.normalize_token(entered)

        else:
            click.echo("Starting browser authentication...")
            captured_token = Auth().browser(timeout=timeout)

            if captured_token:
                captured_token = BearerTokenExtractor.normalize_token(captured_token)

        if not captured_token:
            raise DeepWrapCLIError(
                "Authentication failed: bearer token was not captured."
            )

        if save:
            store = ConfigStore()
            store.update_token(captured_token)
            echo_success(f"Authentication successful. Token saved to: {store.path}")
        else:
            echo_success("Authentication successful. Token was not saved.")

        if show_token:
            click.echo(captured_token)

    except KeyboardInterrupt:
        click.echo()
        raise DeepWrapCLIError("Authentication cancelled.")

    except DeepWrapCLIError:
        raise

    except Exception as exc:
        raise DeepWrapCLIError(f"Authentication failed: {exc}") from exc


@cli.command("api")
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host to bind the API server to.",
)
@click.option(
    "--port",
    default=8000,
    show_default=True,
    type=int,
    help="Port to bind the API server to.",
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload for development.",
)
@click.option(
    "--workers",
    default=1,
    show_default=True,
    type=int,
    help="Number of Uvicorn workers. Ignored when --reload is enabled.",
)
@click.option(
    "--log-level",
    default="info",
    show_default=True,
    type=click.Choice(["critical", "error", "warning", "info", "debug", "trace"]),
    help="Uvicorn log level.",
)
def api_command(
    host: str,
    port: int,
    reload: bool,
    workers: int,
    log_level: str,
) -> None:
    """
    Start the DeepWrap FastAPI server.
    """

    try:
        import uvicorn
    except ImportError as exc:
        raise DeepWrapCLIError(
            "Missing dependency: uvicorn. Install with: pip install fastapi uvicorn"
        ) from exc

    if workers < 1:
        raise DeepWrapCLIError("--workers must be greater than or equal to 1.")

    if reload and workers != 1:
        echo_warning("--workers is ignored when --reload is enabled.")
        workers = 1

    uvicorn.run(
        "deepwrap.interfaces.api:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level=log_level,
    )


@cli.command("chat")
@click.argument("message", nargs=-1, required=True)
@click.option(
    "--token",
    type=str,
    default=None,
    help="Bearer token. If omitted, DeepWrap loads the saved config token.",
)
@click.option(
    "--model",
    type=click.Choice(SUPPORTED_MODELS),
    default="expert",
    show_default=True,
)
@click.option(
    "--thinking/--no-thinking",
    default=True,
    show_default=True,
    help="Enable or disable thinking output.",
)
@click.option(
    "--search/--no-search",
    default=True,
    show_default=True,
    help="Enable or disable search.",
)
@click.option(
    "--god/--no-god",
    default=False,
    show_default=True,
    help="Enable or disable God Mode for this chat session.",
)
@click.option(
    "--stream/--no-stream",
    default=False,
    show_default=True,
    help="Stream response chunks instead of printing after completion.",
)
def chat_command(
    message: tuple[str, ...],
    token: Optional[str],
    model: str,
    thinking: bool,
    search: bool,
    god: bool,
    stream: bool,
) -> None:
    """
    Send a single non-interactive chat request.
    """

    text = " ".join(message).strip()

    if not text:
        raise DeepWrapCLIError("Message cannot be empty.")

    try:
        resolved_token = resolve_token(token)

        client = Client(api_key=resolved_token)
        chat = client.chats.create_session(
            model=model,
            god_mode=god,
        )

        response = chat.respond(
            text,
            thinking=thinking,
            search=search,
            stream=stream,
        )

        if stream:
            for chunk in response:
                click.echo(chunk, nl=False)
            click.echo()
            return

        click.echo(response)

    except DeepWrapCLIError:
        raise

    except KeyboardInterrupt:
        click.echo()
        raise DeepWrapCLIError("Chat cancelled.")

    except Exception as exc:
        raise DeepWrapCLIError(f"Chat failed: {exc}") from exc


@cli.command("config")
def config_command() -> None:
    """
    Show DeepWrap config location and basic status.
    """

    try:
        store = ConfigStore()
        config = store.load()

        click.echo(f"Config path: {store.path}")
        click.echo(f"Token configured: {'yes' if config.token else 'no'}")

        if getattr(config, "model", None):
            click.echo(f"Default model: {config.model}")

        if hasattr(config, "show_thinking"):
            click.echo(f"Show thinking: {'yes' if config.show_thinking else 'no'}")

        if hasattr(config, "search_enabled"):
            click.echo(f"Search enabled: {'yes' if config.search_enabled else 'no'}")

        if hasattr(config, "god_mode"):
            click.echo(f"God Mode: {'yes' if config.god_mode else 'no'}")

    except Exception as exc:
        raise DeepWrapCLIError(f"Failed to read config: {exc}") from exc


def main() -> None:
    try:
        cli()

    except DeepWrapCLIError as exc:
        echo_error(f"Error: {exc.message}")
        sys.exit(exc.exit_code)

    except KeyboardInterrupt:
        click.echo()
        echo_warning("Cancelled.")
        sys.exit(130)


if __name__ == "__main__":
    main()