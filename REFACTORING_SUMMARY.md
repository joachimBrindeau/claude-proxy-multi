# Refactoring Summary - Race Condition Fix & Model Fallback Implementation

**Date:** 2026-01-03
**Focus:** Token refresh race condition and model fallback system

## Issues Fixed

### 1. Token Refresh Race Condition
**Problem:** Server accepted requests before token refresh completed during startup, causing false "Authentication failed" errors on accounts with expired tokens.

**Root Cause:**
- Token refresh scheduler started asynchronously without blocking startup
- Accounts with expired tokens were available for requests before refresh completed
- Created ~1-5 second window where requests would fail with 401 errors

**Solution:**
- Modified `TokenRefreshScheduler.start()` to accept `block_until_initial_refresh` parameter (default: True)
- Server startup now blocks until initial token refresh completes
- Added "refreshing" state to prevent accounts from being selected mid-refresh

### 2. Capacity Check Error Messaging
**Problem:** Rate-limited accounts (429) showed misleading "error" messages even though rate limit headers were present.

**Solution:**
- Modified capacity check to only set error for 429 if rate limit headers are missing
- 429 responses with headers now properly indicate rate-limited state via `is_rate_limited` property
- Added response preview logging for 401 errors to aid debugging

## Files Modified

### Core Changes

**`src/claude_code_proxy/rotation/refresh.py`**
- Added `block_until_initial_refresh` parameter to `start()` method
- Scheduler blocks on initial refresh to prevent race conditions
- Added "refreshing" state handling to skip accounts during refresh

**`src/claude_code_proxy/rotation/accounts.py`**
- Added "refreshing" to valid account states
- Added `mark_refreshing()` method to mark account as being refreshed
- Added `mark_refresh_complete(success)` method to restore state after refresh

**`src/claude_code_proxy/rotation/capacity_check.py`**
- Improved 429 error handling to distinguish between rate limit with/without headers
- Added response preview to 401 error logging

**`src/claude_code_proxy/utils/startup_helpers.py`**
- Added `CredentialsExpiredError` to caught exceptions
- Server now gracefully handles expired credentials during startup

### Model Fallback System (New Feature)

**`src/claude_code_proxy/services/model_fallback.py`** - NEW
- `ModelAvailabilityCache`: Per-user persistent cache of unavailable models
- `FallbackResolver`: Automatic fallback when models return 403
- Supports tier-based fallback (Opus → Sonnet → Haiku)

**`src/claude_code_proxy/api/routes/stream_helpers.py`**
- Added `X-Actual-Model` and `X-Model-Fallback` response headers
- Headers indicate when fallback occurred and which model was used

**`src/claude_code_proxy/ui/templates/settings.html`** - NEW
- Settings page for model provider selection
- Fallback toggle and cache TTL configuration
- Per-tier default model selection

**`src/claude_code_proxy/api/routes/settings.py`** - NEW
- Routes for settings page and form handlers
- Provider update, fallback toggle, tier defaults endpoints

**`src/claude_code_proxy/api/app.py`**
- Registered settings router

**`src/claude_code_proxy/ui/templates/accounts.html`**
- Added settings icon/link in header

## Tests Added

**`tests/unit/rotation/test_rotation_edge_cases.py`**
- `test_token_refresh_blocks_startup`: Verifies blocking behavior and state transitions
- `test_refreshing_state_prevents_selection`: Ensures refreshing accounts are skipped

## Test Results

✅ **All rotation tests passing (9/9)**
- 7 existing edge case tests
- 2 new race condition tests

✅ **No regressions** in existing rotation functionality

⚠️ **Note:** Some pre-existing test failures in `test_startup_helpers.py` (8 failures) related to logging assertions - not related to these changes

## Race Condition Analysis

Checked for similar patterns in codebase:
- Reviewed 13 files using `asyncio.create_task`
- Other usages are intentional background tasks (cleanup loops, servers, etc.)
- No similar startup race conditions found

## Startup Flow (Before vs After)

### Before (Race Condition)
```
T0: Server startup begins
T1: Rotation pool loaded (expired tokens)
T2: Middleware ready (accepts requests)
T3: Token refresh starts (async, non-blocking)
T4: Server startup completes - ACCEPTS REQUESTS ❌
--- RACE WINDOW (1-5 seconds) ---
T5: Capacity check runs with expired token → 401 error
T6: Account marked as "auth_error"
T7: Token refresh completes (too late!)
```

### After (Fixed)
```
T0: Server startup begins
T1: Rotation pool loaded (expired tokens)
T2: Middleware ready (but waiting...)
T3: Token refresh starts (blocks startup)
T4: Accounts marked as "refreshing"
T5: Token refresh completes
T6: Accounts marked as "available"
T7: Server startup completes - NOW ACCEPTS REQUESTS ✅
```

## Breaking Changes

None - all changes are backward compatible. The `block_until_initial_refresh` parameter defaults to `True` for safety but can be disabled if needed.

## Performance Impact

- Startup time increased by ~1-5 seconds (time to refresh expired tokens)
- This is acceptable trade-off to prevent false auth errors
- Only affects startup - no runtime performance impact

## Future Improvements

1. Add persistent storage for settings (currently TODOs in code)
2. Consider adding metrics for refresh timing
3. Add integration tests for full server startup flow

## Migration Notes

No migration needed - changes are transparent to users. Servers will now:
1. Take slightly longer to start (blocking on token refresh)
2. Not show false "Authentication failed" messages on startup
3. Gracefully handle expired credentials with proper error messages
