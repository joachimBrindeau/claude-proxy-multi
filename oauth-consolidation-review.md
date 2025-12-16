# OAuth Configuration Consolidation - Code Review

**Date**: 2025-12-14
**Reviewer**: Claude Code Review Agent
**Scope**: OAuth configuration consolidation across ccproxy-multi codebase

## Executive Summary

The OAuth configuration consolidation successfully created a single source of truth in `ccproxy/auth/oauth/constants.py`. However, there is a CRITICAL scope/redirect URI mismatch between modules that must be resolved before merge.

## Critical Issues (Must Fix Before Merge)

### 1. Scope/Redirect URI Mismatch - config/auth.py

**Problem**: `ccproxy/config/auth.py` uses localhost redirect URI but imports scopes optimized for console redirect URI. This creates an incompatible configuration.

**Files Affected**:
- `ccproxy/config/auth.py:61` - hardcodes `http://localhost:54545/callback`
- `ccproxy/config/auth.py:65` - imports `OAUTH_SCOPES` (excludes `org:create_api_key`)

**Why This Breaks**:
According to the constants documentation:
- Console redirect: CANNOT include `org:create_api_key` 
- Localhost redirect: CAN include `org:create_api_key`

Current state creates a mismatch where localhost redirect is used without the scope it supports.

**Recommended Fix**: Import and use `OAUTH_REDIRECT_URI` from constants

```python
# ccproxy/config/auth.py
from ccproxy.auth.oauth.constants import (
    OAUTH_AUTHORIZE_URL,
    OAUTH_BETA_VERSION,
    OAUTH_CLIENT_ID,
    OAUTH_REDIRECT_URI,  # ADD THIS
    OAUTH_SCOPES,
    OAUTH_TOKEN_URL,
    OAUTH_USER_AGENT,
)

class OAuthSettings(BaseModel):
    redirect_uri: str = Field(
        default=OAUTH_REDIRECT_URI,  # Use constant instead of localhost
        description="OAuth redirect URI (from shared constants)",
    )
```

**Alternative Fix**: Create separate localhost constants if callback server is required.

## High Priority Issues

### 2. Incomplete Migration - rotation/refresh.py

**File**: `ccproxy/rotation/refresh.py:14`

**Problem**: Still imports from `token_exchange.py` instead of `constants.py`

```python
# Current (wrong)
from ccproxy.auth.oauth.token_exchange import OAUTH_CLIENT_ID, OAUTH_TOKEN_URL

# Should be
from ccproxy.auth.oauth.constants import OAUTH_CLIENT_ID, OAUTH_TOKEN_URL
```

### 3. Type Mismatch - oauth_client.py

**File**: `ccproxy/services/credentials/oauth_client.py:70-76`

**Problem**: Type hint says `OAuthSettings` but defaults to `OAuthConfig()`

```python
# Current (type mismatch)
def __init__(self, config: OAuthSettings | None = None):
    self.config = config or OAuthConfig()

# Should be
def __init__(self, config: OAuthConfig | None = None):
    self.config = config or OAuthConfig()
```

## Medium Priority Issues

### 4. Duplicate OAuth Config Classes

**Problem**: Three different OAuth config classes exist:
- `ccproxy.config.auth.OAuthSettings`
- `ccproxy.services.credentials.config.OAuthConfig`
- `ccproxy.auth.oauth.token_exchange.OAuthConfig` (dataclass)

**Recommendation**: Consolidate to single class in `token_exchange.py`

### 5. Missing Migration Documentation

**File**: `ccproxy/auth/oauth/constants.py`

**Recommendation**: Add migration guide section explaining when to use localhost vs console redirect.

## Suggestions

1. **Add Runtime Validation**: Create `validate_oauth_config()` function to catch mismatches
2. **Add Integration Tests**: Test that all configs use shared constants consistently
3. **Factory Methods**: Add `OAuthConfig.for_localhost()` and `OAuthConfig.for_console()` helpers

## Strengths

1. Excellent documentation in constants.py with HAR analysis evidence
2. Consistent import patterns in updated files
3. Smart choice of console redirect as default for maximum compatibility
4. Well-structured constants module

## Files Successfully Updated

- `ccproxy/auth/oauth/constants.py` - Created as single source of truth
- `ccproxy/auth/oauth/token_exchange.py` - Imports from constants
- `ccproxy/services/credentials/config.py` - Imports from constants
- `ccproxy/ui/accounts.py` - Imports from constants

## Files Needing Updates

- `ccproxy/config/auth.py` - Redirect URI mismatch (CRITICAL)
- `ccproxy/rotation/refresh.py` - Wrong import source (HIGH)
- `ccproxy/services/credentials/oauth_client.py` - Type mismatch (HIGH)

## Verification Checklist

- [x] Fix redirect URI in config/auth.py
- [x] Update imports in rotation/refresh.py
- [x] Fix type hint in oauth_client.py
- [ ] Add integration test for config consistency
- [ ] Consider consolidating OAuth config classes

## Conclusion

The consolidation work is well-executed with excellent documentation. The critical issue with config/auth.py must be resolved to prevent authentication failures. Once fixed, this will successfully eliminate scope divergence across the codebase.
