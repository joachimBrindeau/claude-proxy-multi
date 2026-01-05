#!/usr/bin/env python3
"""
Standalone test script to check capacity check endpoint responses.

Tests both accounts to see what headers and status codes are returned.
"""

import json
from typing import Any

import httpx


BASE_URL = "http://localhost:8089"
ENDPOINT = "/api/v1/messages"


def make_request(account_name: str) -> dict[str, Any]:
    """Make a minimal request to the capacity check endpoint."""
    url = f"{BASE_URL}{ENDPOINT}"
    headers = {
        "Content-Type": "application/json",
        "X-Account-Name": account_name,
    }

    # Minimal request payload
    payload = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "Hi"}],
    }

    print(f"\n{'=' * 80}")
    print(f"Testing account: {account_name}")
    print(f"{'=' * 80}")
    print(f"\nRequest URL: {url}")
    print(f"Request Headers: {json.dumps(headers, indent=2)}")
    print(f"Request Payload: {json.dumps(payload, indent=2)}")

    try:
        response = httpx.post(
            url, headers=headers, json=payload, timeout=30.0, follow_redirects=True
        )

        print("\n--- Response ---")
        print(f"Status Code: {response.status_code}")
        print("\nAll Response Headers:")
        for key, value in sorted(response.headers.items()):
            print(f"  {key}: {value}")

        # Highlight rate limit headers
        print("\n--- Rate Limit Headers ---")
        rate_limit_headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower().startswith("anthropic-ratelimit-")
        }
        if rate_limit_headers:
            for key, value in sorted(rate_limit_headers.items()):
                print(f"  {key}: {value}")
        else:
            print("  No anthropic-ratelimit-* headers found")

        print("\n--- Response Body ---")
        try:
            body = response.json()
            print(json.dumps(body, indent=2))
        except Exception:
            print(f"Raw text: {response.text}")

        return {
            "account": account_name,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "rate_limit_headers": rate_limit_headers,
            "body": response.text,
        }

    except Exception as e:
        print("\n--- Error ---")
        print(f"Error making request: {e}")
        return {"account": account_name, "error": str(e)}


def main() -> None:
    """Test both accounts and compare results."""
    print("=" * 80)
    print("Claude Proxy Capacity Check Test")
    print("=" * 80)
    print("\nThis script tests the capacity check endpoint for multiple accounts")
    print("to observe differences in rate limit headers and responses.\n")

    accounts = ["klarc-joachim", "klarc-contact"]
    results = []

    for account in accounts:
        result = make_request(account)
        results.append(result)

    # Summary comparison
    print(f"\n{'=' * 80}")
    print("SUMMARY COMPARISON")
    print(f"{'=' * 80}\n")

    for result in results:
        if "error" in result:
            print(f"Account: {result['account']}")
            print(f"  Error: {result['error']}\n")
        else:
            print(f"Account: {result['account']}")
            print(f"  Status Code: {result['status_code']}")
            print(f"  Has Rate Limit Headers: {bool(result['rate_limit_headers'])}")
            if result["rate_limit_headers"]:
                print("  Rate Limit Headers:")
                for key, value in sorted(result["rate_limit_headers"].items()):
                    print(f"    {key}: {value}")
            print()


if __name__ == "__main__":
    main()
