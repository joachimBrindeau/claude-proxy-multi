"""Display helpers for authentication commands.

This module contains helper functions to format and display credential information,
reducing complexity in the main auth commands.
"""

from datetime import UTC, datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table

from claude_code_proxy.models.credentials import ClaudeAIOAuth
from claude_code_proxy.models.user_profile import AccountProfile


def format_time_remaining(expires_at: datetime) -> str:
    """Format time remaining until expiration.

    Args:
        expires_at: Expiration datetime

    Returns:
        Formatted string with time remaining or "Expired"
    """
    now = datetime.now(UTC)
    time_diff = expires_at - now

    if time_diff.total_seconds() <= 0:
        return "[red]Expired[/red]"

    days = time_diff.days
    hours = (time_diff.seconds % 86400) // 3600
    minutes = (time_diff.seconds % 3600) // 60

    return f"{days} days, {hours} hours, {minutes} minutes"


def display_account_section(
    console: Console,
    oauth: ClaudeAIOAuth,
    profile: AccountProfile | None,
) -> None:
    """Display the account section with login method and profile information.

    Args:
        console: Rich console for output
        oauth: OAuth token information
        profile: Account profile (may be None if unavailable)
    """
    console.print("\n[bold]Account[/bold]")

    # Login method based on subscription type
    login_method = "Claude Account"
    if oauth.subscription_type:
        login_method = f"Claude {oauth.subscription_type.title()} Account"
    console.print(f"  L Login Method: {login_method}")

    if not profile:
        console.print("  L Organization: [dim]Unable to fetch[/dim]")
        console.print("  L Email: [dim]Unable to fetch[/dim]")
        return

    # Display organization information
    if profile.organization:
        console.print(f"  L Organization: {profile.organization.name}")
        if profile.organization.organization_type:
            console.print(
                f"  L Organization Type: {profile.organization.organization_type}"
            )
        if profile.organization.billing_type:
            console.print(f"  L Billing Type: {profile.organization.billing_type}")
        if profile.organization.rate_limit_tier:
            console.print(
                f"  L Rate Limit Tier: {profile.organization.rate_limit_tier}"
            )
    else:
        console.print("  L Organization: [dim]Not available[/dim]")

    # Display account information
    if profile.account:
        console.print(f"  L Email: {profile.account.email}")
        if profile.account.full_name:
            console.print(f"  L Full Name: {profile.account.full_name}")
        if profile.account.display_name:
            console.print(f"  L Display Name: {profile.account.display_name}")
        console.print(
            f"  L Has Claude Pro: {'Yes' if profile.account.has_claude_pro else 'No'}"
        )
        console.print(
            f"  L Has Claude Max: {'Yes' if profile.account.has_claude_max else 'No'}"
        )
    else:
        console.print("  L Email: [dim]Not available[/dim]")


def create_credential_details_table(
    oauth: ClaudeAIOAuth,
    cred_file: Path | None,
    has_account_profile: bool,
) -> Table:
    """Create a Rich table with credential details.

    Args:
        oauth: OAuth token information
        cred_file: Path to credential file (None if using keyring)
        has_account_profile: Whether an account profile exists

    Returns:
        Formatted Rich table with credential details
    """
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.ROUNDED,
        title="Credential Details",
        title_style="bold white",
    )
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    # File location
    if cred_file:
        table.add_row("File Location", str(cred_file))
    else:
        table.add_row("File Location", "Keyring storage")

    # Token info
    table.add_row("Subscription Type", oauth.subscription_type or "Unknown")
    table.add_row(
        "Token Expired",
        "[red]Yes[/red]" if oauth.is_expired else "[green]No[/green]",
    )

    # Expiration details
    exp_dt = oauth.expires_at_datetime
    table.add_row("Expires At", exp_dt.strftime("%Y-%m-%d %H:%M:%S UTC"))
    table.add_row("Time Remaining", format_time_remaining(exp_dt))

    # Scopes
    if oauth.scopes:
        table.add_row("OAuth Scopes", ", ".join(oauth.scopes))

    # Token preview (first and last 8 chars)
    if oauth.access_token:
        token_preview = f"{oauth.access_token[:8]}...{oauth.access_token[-8:]}"
        table.add_row("Access Token", f"[dim]{token_preview}[/dim]")

    # Account profile status
    table.add_row(
        "Account Profile",
        "[green]Available[/green]"
        if has_account_profile
        else "[yellow]Not saved[/yellow]",
    )

    return table


def display_no_credentials_message(console: Console, storage_paths: list[Path]) -> None:
    """Display a message when no credentials are found.

    Args:
        console: Rich console for output
        storage_paths: List of paths that were checked
    """
    console.print("\n[dim]Expected locations:[/dim]")
    for path in storage_paths:
        console.print(f"  - {path}")
