# src/claude_code_proxy/cli/commands/api_keys.py
"""CLI commands for API key management."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from claude_code_proxy.auth.api_keys import APIKeyCreate, APIKeyManager
from claude_code_proxy.config.settings import get_settings


console = Console()


def get_manager() -> APIKeyManager:
    """Get API key manager from settings."""
    settings = get_settings()

    if not settings.security.api_keys_enabled:
        console.print("[red]API keys are not enabled.[/red]")
        console.print("Set SECURITY__API_KEYS_ENABLED=true to enable.")
        raise typer.Exit(1)

    if not settings.security.api_key_secret:
        console.print("[red]API key secret not configured.[/red]")
        raise typer.Exit(1)

    storage_path = Path(settings.auth.storage.api_keys_file)
    return APIKeyManager(
        storage_path=storage_path,
        secret_key=settings.security.api_key_secret,
    )


def create_key(
    user: str = typer.Option(..., "--user", "-u", help="User ID for the key"),
    description: str = typer.Option("", "--description", "-d", help="Key description"),
    expires_days: int = typer.Option(
        90, "--expires", "-e", help="Days until expiration"
    ),
) -> None:
    """Create a new API key for a user."""
    manager = get_manager()

    request = APIKeyCreate(
        user_id=user,
        description=description,
        expires_days=expires_days,
    )

    key, token = manager.create_key(request)

    console.print()
    console.print("[green]API key created successfully![/green]")
    console.print()
    console.print(f"[bold]Key ID:[/bold] {key.key_id}")
    console.print(f"[bold]User:[/bold] {key.user_id}")
    console.print(
        f"[bold]Expires:[/bold] {key.expires_at.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    console.print()
    console.print("[yellow]Save this token - it will not be shown again:[/yellow]")
    console.print()
    console.print(f"[bold cyan]{token}[/bold cyan]")
    console.print()


def list_keys() -> None:
    """List all API keys."""
    manager = get_manager()
    keys = manager.list_keys()

    if not keys:
        console.print("[yellow]No API keys found.[/yellow]")
        return

    table = Table(title="API Keys")
    table.add_column("Key ID", style="cyan")
    table.add_column("User", style="green")
    table.add_column("Description")
    table.add_column("Created")
    table.add_column("Expires")
    table.add_column("Status")

    for key in keys:
        status = "[red]Revoked[/red]" if key.revoked else "[green]Active[/green]"
        table.add_row(
            key.key_id,
            key.user_id,
            key.description or "-",
            key.created_at.strftime("%Y-%m-%d"),
            key.expires_at.strftime("%Y-%m-%d"),
            status,
        )

    console.print(table)


def revoke_key(
    key_id: str = typer.Option(..., "--key-id", "-k", help="Key ID to revoke"),
) -> None:
    """Revoke an API key."""
    manager = get_manager()

    if manager.revoke_key(key_id):
        console.print(f"[green]Key {key_id} has been revoked.[/green]")
    else:
        console.print(f"[red]Key {key_id} not found.[/red]")
        raise typer.Exit(1)


def delete_key(
    key_id: str = typer.Option(..., "--key-id", "-k", help="Key ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Permanently delete an API key."""
    if not force:
        confirm = typer.confirm(f"Permanently delete key {key_id}?")
        if not confirm:
            raise typer.Abort()

    manager = get_manager()

    if manager.delete_key(key_id):
        console.print(f"[green]Key {key_id} has been deleted.[/green]")
    else:
        console.print(f"[red]Key {key_id} not found.[/red]")
        raise typer.Exit(1)
