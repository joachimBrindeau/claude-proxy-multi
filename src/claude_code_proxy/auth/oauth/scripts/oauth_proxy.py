#!/usr/bin/env python3
"""Local OAuth callback proxy for Claude account management.

This script runs a local HTTP server that catches OAuth callbacks from Claude
and forwards them to your remote claude-code-proxy server.

Usage:
    python oauth_proxy.py [SERVER_URL]

    SERVER_URL: Your claude-code-proxy server URL (default: http://localhost:8000)

Example:
    # Using default server
    python oauth_proxy.py

    # Custom server
    python oauth_proxy.py https://my-server.example.com

Then go to your server's /accounts page and click "Add Account".

"""

import http.server
import sys
import urllib.parse
import webbrowser
from typing import Any


# Configuration
DEFAULT_SERVER = "http://localhost:8000"
LISTEN_PORT = 54545
LISTEN_HOST = "localhost"


class OAuthProxyHandler(http.server.BaseHTTPRequestHandler):
    """Handler that redirects OAuth callbacks to the remote server."""

    server_url: str = DEFAULT_SERVER

    def do_GET(self) -> None:
        """Handle GET requests - redirect callbacks to server."""
        # Parse the request path
        parsed = urllib.parse.urlparse(self.path)

        # Handle favicon requests
        if parsed.path == "/favicon.ico":
            self.send_response(404)
            self.end_headers()
            return

        # Handle the OAuth callback
        if parsed.path == "/callback":
            # Get query parameters
            query = parsed.query

            # Build redirect URL to server
            redirect_url = f"{self.server_url}/oauth/callback?{query}"

            print(f"\n{'=' * 60}")
            print("OAuth callback received!")
            print(f"Redirecting to: {redirect_url}")
            print(f"{'=' * 60}\n")

            # Send redirect response
            self.send_response(302)
            self.send_header("Location", redirect_url)
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()

            # Write a simple HTML page in case redirect doesn't work
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Redirecting...</title>
    <meta http-equiv="refresh" content="0;url={redirect_url}">
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }}
    </style>
</head>
<body>
    <h1>Redirecting...</h1>
    <p>If you're not redirected automatically, <a href="{redirect_url}">click here</a>.</p>
</body>
</html>"""
            self.wfile.write(html.encode())
            return

        # Handle root path - show status
        if parsed.path == "/" or parsed.path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()

            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>OAuth Proxy Running</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
        .status {{ color: #22c55e; font-size: 24px; }}
        code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }}
        .config {{ background: #f8fafc; padding: 16px; border-radius: 8px; margin: 16px 0; }}
    </style>
</head>
<body>
    <h1><span class="status">●</span> OAuth Proxy Running</h1>

    <div class="config">
        <p><strong>Listening on:</strong> <code>http://{LISTEN_HOST}:{LISTEN_PORT}</code></p>
        <p><strong>Forwarding to:</strong> <code>{self.server_url}</code></p>
    </div>

    <h2>How to use:</h2>
    <ol>
        <li>Keep this terminal running</li>
        <li>Go to <a href="{self.server_url}/accounts" target="_blank">{self.server_url}/accounts</a></li>
        <li>Click "Add Account" and sign in with Google</li>
        <li>You'll be redirected back here, then to your server</li>
    </ol>

    <p><em>Waiting for OAuth callback...</em></p>
</body>
</html>"""
            self.wfile.write(html.encode())
            return

        # Unknown path
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not found")

    def log_message(self, format: str, *args: Any) -> None:
        """Format and print log messages."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    """Run the OAuth proxy server."""
    # Get server URL from command line or use default
    server_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER

    # Remove trailing slash
    server_url = server_url.rstrip("/")

    # Set the server URL on the handler class
    OAuthProxyHandler.server_url = server_url

    # Create and start server
    server = http.server.HTTPServer((LISTEN_HOST, LISTEN_PORT), OAuthProxyHandler)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    OAuth Callback Proxy                       ║
╠══════════════════════════════════════════════════════════════╣
║  Listening on: http://{LISTEN_HOST}:{LISTEN_PORT:<26}║
║  Forwarding to: {server_url:<43}║
╠══════════════════════════════════════════════════════════════╣
║  Instructions:                                                ║
║  1. Keep this terminal running                                ║
║  2. Go to {server_url}/accounts{" ":<31}║
║  3. Click "Add Account" and sign in with Google               ║
║  4. The callback will be forwarded to your server             ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Open browser to show status page
    print("Opening status page in browser...")
    webbrowser.open(f"http://{LISTEN_HOST}:{LISTEN_PORT}")

    print("\nPress Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nStopping proxy server...")
        server.shutdown()
        print("Goodbye!")


if __name__ == "__main__":
    main()
