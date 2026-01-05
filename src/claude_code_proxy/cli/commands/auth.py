"""Authentication and credential management commands."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich import box
from rich.console import Console
from rich.table import Table
from structlog import get_logger

from claude_code_proxy.cli.commands.api_keys import (
    create_key,
    delete_key,
    list_keys,
    revoke_key,
)
from claude_code_proxy.cli.helpers import get_rich_toolkit
from claude_code_proxy.config.settings import get_settings
from claude_code_proxy.core.async_utils import get_claude_docker_home_dir
from claude_code_proxy.exceptions import (
    CredentialsError,
    CredentialsNotFoundError,
    CredentialsStorageError,
    OAuthError,
)
from claude_code_proxy.services.credentials import CredentialsManager


app = typer.Typer(name="auth", help="Authentication and credential management")

console = Console()
logger = get_logger(__name__)


def get_credentials_manager(
    custom_paths: list[Path] | None = None,
) -> CredentialsManager:
    """Get a CredentialsManager instance with custom paths if provided."""
    if custom_paths:
        # Get base settings and update storage paths
        settings = get_settings()
        settings.auth.storage.storage_paths = custom_paths
        return CredentialsManager(config=settings.auth)
    # Use default settings
    settings = get_settings()
    return CredentialsManager(config=settings.auth)


def get_docker_credential_paths() -> list[Path]:
    """Get credential file paths for Docker environment."""
    docker_home = Path(get_claude_docker_home_dir())
    return [
        docker_home / ".claude" / ".credentials.json",
        docker_home / ".config" / "claude" / ".credentials.json",
        Path(".credentials.json"),
    ]


def _resolve_credential_paths(
    docker: bool,
    credential_file: str | None,
) -> list[Path] | None:
    """Resolve credential paths based on command options.

    Args:
        docker: Whether to use Docker credential paths
        credential_file: Path to specific credential file

    Returns:
        List of credential paths, or None for default paths

    """
    if credential_file:
        return [Path(credential_file)]
    if docker:
        return get_docker_credential_paths()
    return None


@app.command(name="validate")
def validate_credentials(
    docker: Annotated[
        bool,
        typer.Option(
            "--docker",
            help="Use Docker credential paths (from get_claude_docker_home_dir())",
        ),
    ] = False,
    credential_file: Annotated[
        str | None,
        typer.Option(
            "--credential-file",
            help="Path to specific credential file to validate",
        ),
    ] = None,
) -> None:
    """Validate Claude CLI credentials.

    Checks for valid Claude credentials in standard locations:
    - ~/.claude/credentials.json
    - ~/.config/claude/credentials.json

    With --docker flag, checks Docker credential paths:
    - {docker_home}/.claude/credentials.json
    - {docker_home}/.config/claude/credentials.json

    With --credential-file, validates the specified file directly.

    Examples:
        claude-code-proxy auth validate
        claude-code-proxy auth validate --docker
        claude-code-proxy auth validate --credential-file /path/to/credentials.json

    """
    toolkit = get_rich_toolkit()
    toolkit.print("[bold cyan]Claude Credentials Validation[/bold cyan]", centered=True)
    toolkit.print_line()

    try:
        # Get credential paths and validate credentials
        custom_paths = _resolve_credential_paths(docker, credential_file)
        manager = get_credentials_manager(custom_paths)
        validation_result = asyncio.run(manager.validate())

        if validation_result.valid:
            # Create a status table
            table = Table(
                show_header=True,
                header_style="bold cyan",
                box=box.ROUNDED,
                title="Credential Status",
                title_style="bold white",
            )
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            # Status
            status = "Valid" if not validation_result.expired else "Expired"
            status_style = "green" if not validation_result.expired else "red"
            table.add_row("Status", f"[{status_style}]{status}[/{status_style}]")

            # Path
            if validation_result.path:
                table.add_row("Location", f"[dim]{validation_result.path}[/dim]")

            # Subscription type
            if validation_result.credentials:
                sub_type = (
                    validation_result.credentials.claude_ai_oauth.subscription_type
                    or "Unknown"
                )
                table.add_row("Subscription", f"[bold]{sub_type}[/bold]")

                # Expiration
                oauth_token = validation_result.credentials.claude_ai_oauth
                exp_dt = oauth_token.expires_at_datetime
                now = datetime.now(UTC)
                time_diff = exp_dt - now

                if time_diff.total_seconds() > 0:
                    days = time_diff.days
                    hours = time_diff.seconds // 3600
                    exp_str = f"{exp_dt.strftime('%Y-%m-%d %H:%M:%S UTC')} ({days}d {hours}h remaining)"
                else:
                    exp_str = f"{exp_dt.strftime('%Y-%m-%d %H:%M:%S UTC')} [red](Expired)[/red]"

                table.add_row("Expires", exp_str)

                # Scopes
                scopes = oauth_token.scopes
                if scopes:
                    table.add_row("Scopes", ", ".join(str(s) for s in scopes))

            console.print(table)

            # Success message
            if not validation_result.expired:
                toolkit.print(
                    "[green]✓[/green] Valid Claude credentials found", tag="success"
                )
            else:
                toolkit.print(
                    "[yellow]![/yellow] Claude credentials found but expired",
                    tag="warning",
                )
                toolkit.print(
                    "\nPlease refresh your credentials by logging into Claude CLI",
                    tag="info",
                )

        else:
            # No valid credentials
            toolkit.print("[red]✗[/red] No credentials file found", tag="error")

            console.print("\n[dim]To authenticate with Claude CLI, run:[/dim]")
            console.print("[cyan]claude login[/cyan]")

    except (CredentialsError, CredentialsStorageError, OSError) as e:
        # Credential loading/storage errors or file system errors
        toolkit.print(f"Error validating credentials: {e}", tag="error")
        raise typer.Exit(1) from e
    except Exception as e:
        toolkit.print(f"Error validating credentials: {e}", tag="error")
        raise typer.Exit(1) from e


@app.command(name="info")
def credential_info(
    docker: Annotated[
        bool,
        typer.Option(
            "--docker",
            help="Use Docker credential paths (from get_claude_docker_home_dir())",
        ),
    ] = False,
    credential_file: Annotated[
        str | None,
        typer.Option(
            "--credential-file",
            help="Path to specific credential file to display info for",
        ),
    ] = None,
) -> None:
    """Display detailed credential information.

    Shows all available information about Claude credentials including
    file location, token details, and subscription information.

    Examples:
        claude-code-proxy auth info
        claude-code-proxy auth info --docker
        claude-code-proxy auth info --credential-file /path/to/credentials.json

    """
    from claude_code_proxy.cli.commands.auth_credential_helpers import get_profile_sync
    from claude_code_proxy.cli.commands.auth_display_helpers import (
        create_credential_details_table,
        display_account_section,
        display_no_credentials_message,
    )

    toolkit = get_rich_toolkit()
    toolkit.print("[bold cyan]Claude Credential Information[/bold cyan]", centered=True)
    toolkit.print_line()

    try:
        # Get credential paths and load credentials
        custom_paths = _resolve_credential_paths(docker, credential_file)
        manager = get_credentials_manager(custom_paths)
        credentials = asyncio.run(manager.load())

        if not credentials:
            toolkit.print("No credential file found", tag="error")
            display_no_credentials_message(
                console, manager.config.storage.storage_paths
            )
            raise typer.Exit(1)

        # Get OAuth token info
        oauth = credentials.claude_ai_oauth

        # Get or fetch account profile
        profile = get_profile_sync(manager)

        # Display account section
        display_account_section(console, oauth, profile)

        # Get credential file location
        cred_file = asyncio.run(manager.find_credentials_file())

        # Create and display details table
        console.print()
        table = create_credential_details_table(
            oauth=oauth,
            cred_file=cred_file,
            has_account_profile=profile is not None,
        )
        console.print(table)

    except (CredentialsError, CredentialsStorageError, OSError) as e:
        toolkit.print(f"Error getting credential info: {e}", tag="error")
        raise typer.Exit(1) from e


@app.command(name="login")
def login_command(
    docker: Annotated[
        bool,
        typer.Option(
            "--docker",
            help="Use Docker credential paths (from get_claude_docker_home_dir())",
        ),
    ] = False,
    credential_file: Annotated[
        str | None,
        typer.Option(
            "--credential-file",
            help="Path to specific credential file to save to",
        ),
    ] = None,
) -> None:
    """Login to Claude using OAuth authentication.

    This command will open your web browser to authenticate with Claude
    and save the credentials locally.

    Examples:
        claude-code-proxy auth login
        claude-code-proxy auth login --docker
        claude-code-proxy auth login --credential-file /path/to/credentials.json

    """
    toolkit = get_rich_toolkit()
    toolkit.print("[bold cyan]Claude OAuth Login[/bold cyan]", centered=True)
    toolkit.print_line()

    try:
        custom_paths = _get_credential_paths(docker, credential_file)
        manager = get_credentials_manager(custom_paths)

        if not _check_should_proceed_with_login(manager):
            return

        success = _perform_oauth_login(manager)

        if success:
            _display_login_success(toolkit, manager)
        else:
            toolkit.print("Login failed. Please try again.", tag="error")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Login cancelled by user.[/yellow]")
        raise typer.Exit(1) from None
    except (OAuthError, CredentialsError, CredentialsStorageError, OSError) as e:
        toolkit.print(f"Error during login: {e}", tag="error")
        raise typer.Exit(1) from e
    except Exception as e:
        toolkit.print(f"Error during login: {e}", tag="error")
        raise typer.Exit(1) from e


def _get_credential_paths(
    docker: bool, credential_file: str | None
) -> list[Path] | None:
    """Get credential paths based on CLI options.

    Args:
        docker: Whether to use Docker credential paths
        credential_file: Optional custom credential file path

    Returns:
        List of credential paths or None for default paths

    """
    if credential_file:
        return [Path(credential_file)]
    if docker:
        return get_docker_credential_paths()
    return None


def _check_should_proceed_with_login(manager: "CredentialsManager") -> bool:
    """Check if user wants to proceed with login when already logged in.

    Args:
        manager: Credentials manager instance

    Returns:
        True if should proceed with login, False otherwise

    """
    try:
        validation_result = asyncio.run(manager.validate())
        if validation_result.valid and not validation_result.expired:
            console.print(
                "[yellow]You are already logged in with valid credentials.[/yellow]"
            )
            console.print(
                "Use [cyan]claude-code-proxy auth info[/cyan] to view current credentials."
            )
            overwrite = typer.confirm(
                "Do you want to login again and overwrite existing credentials?"
            )
            if not overwrite:
                console.print("Login cancelled.")
                return False
    except CredentialsNotFoundError:
        pass  # No credentials found, proceed with login
    return True


def _perform_oauth_login(manager: "CredentialsManager") -> bool:
    """Perform the OAuth login flow.

    Args:
        manager: Credentials manager instance

    Returns:
        True if login succeeded, False otherwise

    """
    console.print("Starting OAuth login process...")
    console.print("Your browser will open for authentication.")
    console.print(
        "A temporary server will start on port 54545 for the OAuth callback..."
    )

    try:
        asyncio.run(manager.login())
        return True
    except (OAuthError, httpx.HTTPError, CredentialsStorageError) as e:
        logger.exception("login_failed", error=str(e), error_type=type(e).__name__)
        return False
    except Exception as e:
        logger.exception(
            "login_failed_unexpected", error=str(e), error_type=type(e).__name__
        )
        return False


def _display_login_success(toolkit: Any, manager: "CredentialsManager") -> None:
    """Display success message and credential info after login.

    Args:
        toolkit: Rich toolkit for formatted output
        manager: Credentials manager instance

    """
    toolkit.print("Successfully logged in to Claude!", tag="success")
    console.print("\n[dim]Credential information:[/dim]")

    updated_validation = asyncio.run(manager.validate())
    if updated_validation.valid and updated_validation.credentials:
        oauth_token = updated_validation.credentials.claude_ai_oauth
        console.print(f"  Subscription: {oauth_token.subscription_type or 'Unknown'}")
        if oauth_token.scopes:
            console.print(f"  Scopes: {', '.join(oauth_token.scopes)}")
        exp_dt = oauth_token.expires_at_datetime
        console.print(f"  Expires: {exp_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")


@app.command()
def renew(
    docker: Annotated[
        bool,
        typer.Option(
            "--docker",
            "-d",
            help="Renew credentials for Docker environment",
        ),
    ] = False,
    credential_file: Annotated[
        Path | None,
        typer.Option(
            "--credential-file",
            "-f",
            help="Path to custom credential file",
        ),
    ] = None,
) -> None:
    """Force renew Claude credentials without checking expiration.

    This command will refresh your access token regardless of whether it's expired.
    Useful for testing or when you want to ensure you have the latest token.

    Examples:
        claude-code-proxy auth renew
        claude-code-proxy auth renew --docker
        claude-code-proxy auth renew --credential-file /path/to/credentials.json

    """
    toolkit = get_rich_toolkit()
    toolkit.print("[bold cyan]Claude Credentials Renewal[/bold cyan]", centered=True)
    toolkit.print_line()

    console = Console()

    try:
        # Get credential paths based on options
        custom_paths = None
        if credential_file:
            custom_paths = [Path(credential_file)]
        elif docker:
            custom_paths = get_docker_credential_paths()

        # Create credentials manager
        manager = get_credentials_manager(custom_paths)

        # Check if credentials exist
        validation_result = asyncio.run(manager.validate())
        if not validation_result.valid:
            toolkit.print("[red]✗[/red] No credentials found to renew", tag="error")
            console.print("\n[dim]Please login first:[/dim]")
            console.print("[cyan]claude-code-proxy auth login[/cyan]")
            raise typer.Exit(1)

        # Force refresh the token
        console.print("[yellow]Refreshing access token...[/yellow]")
        refreshed_credentials = asyncio.run(manager.refresh_token())

        if refreshed_credentials:
            toolkit.print(
                "[green]✓[/green] Successfully renewed credentials!", tag="success"
            )

            # Show updated credential info
            oauth_token = refreshed_credentials.claude_ai_oauth
            console.print("\n[dim]Updated credential information:[/dim]")
            console.print(
                f"  Subscription: {oauth_token.subscription_type or 'Unknown'}"
            )
            if oauth_token.scopes:
                console.print(f"  Scopes: {', '.join(oauth_token.scopes)}")
            exp_dt = oauth_token.expires_at_datetime
            console.print(f"  Expires: {exp_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        else:
            toolkit.print("[red]✗[/red] Failed to renew credentials", tag="error")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Renewal cancelled by user.[/yellow]")
        raise typer.Exit(1) from None
    except (
        OAuthError,
        CredentialsError,
        CredentialsStorageError,
        httpx.HTTPError,
    ) as e:
        # OAuth errors, credential errors, or network errors during token renewal
        toolkit.print(f"Error during renewal: {e}", tag="error")
        raise typer.Exit(1) from e


# Register API key management commands
app.command(name="create-key")(create_key)
app.command(name="list-keys")(list_keys)
app.command(name="revoke-key")(revoke_key)
app.command(name="delete-key")(delete_key)


if __name__ == "__main__":
    app()
