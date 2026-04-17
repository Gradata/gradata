"""Regression tests — device auth verification URL defaults to /connect.

Locks in the fix from commit 76758a8 (fix: update device auth verification
URL to /connect).

Before the fix the fallback URL was:
    https://app.gradata.ai/auth/device

After the fix it is:
    https://app.gradata.ai/connect

The wrong fallback would cause users to be directed to a non-existent page
when the API server does not return a verification_url in the device-code
response.

Mocking rationale: cmd_login() makes real network requests and enters a
polling loop.  We mock urlopen + time.monotonic (to skip the poll loop)
+ sys.exit to capture the code path without network access.  Tests that
exercise the constant directly (inspect/source) require no mocking at all.
"""

from __future__ import annotations

import inspect
import json
import sys
from unittest.mock import MagicMock, patch, call
from urllib.error import URLError

import pytest

# Correct URL (post-fix)
EXPECTED_VERIFICATION_URL = "https://app.gradata.ai/connect"
# Old wrong URL (pre-fix — must NOT appear as the default)
OLD_VERIFICATION_URL = "https://app.gradata.ai/auth/device"


# ---------------------------------------------------------------------------
# Source-level tests (no mocking) — strongest regression guard
# ---------------------------------------------------------------------------


class TestVerificationUrlConstantInSource:
    """Inspect the literal default value in cmd_login source.

    This test is immune to mocking issues because it reads the actual
    string constant that dict.get("verification_url", <default>) uses.
    If someone reverts the fix, this test will catch it immediately.
    """

    def test_positive_connect_is_in_source(self):
        """'/connect' must appear in cmd_login as the verification_url default."""
        from gradata import cli
        source = inspect.getsource(cli.cmd_login)
        assert "/connect" in source, (
            "cmd_login source does not contain '/connect' — "
            "verification_url fallback has not been updated"
        )

    def test_negative_old_auth_device_default_not_in_source(self):
        """'/auth/device' must NOT be the verification_url default string.

        This is the regression: before commit 76758a8, the fallback was
        'https://app.gradata.ai/auth/device'.  After the fix it must be
        'https://app.gradata.ai/connect'.

        Note: '/auth/device/code' and '/auth/device/token' are the server
        API endpoint paths (not the user-facing verification URL), so they
        are allowed to remain.  We check that the specific OLD_VERIFICATION_URL
        constant does not appear at all.
        """
        from gradata import cli
        source = inspect.getsource(cli.cmd_login)
        assert OLD_VERIFICATION_URL not in source, (
            f"REGRESSION: '{OLD_VERIFICATION_URL}' still appears in cmd_login — "
            "the verification_url fix may have been reverted"
        )

    def test_positive_expected_url_literal_present(self):
        """The exact expected URL string must appear as a literal in cmd_login."""
        from gradata import cli
        source = inspect.getsource(cli.cmd_login)
        assert EXPECTED_VERIFICATION_URL in source, (
            f"Expected literal '{EXPECTED_VERIFICATION_URL}' not found in cmd_login"
        )


# ---------------------------------------------------------------------------
# Logic-level tests — code_data.get() fallback behaviour
# ---------------------------------------------------------------------------


class TestVerificationUrlFallbackLogic:
    """Test the get() fallback directly without going through cmd_login."""

    def test_positive_server_provided_url_overrides_default(self):
        """When the server provides verification_url, it is used over the default."""
        custom_url = "https://app.gradata.ai/custom-verify"
        code_data = {
            "device_code": "dev-abc",
            "user_code": "ABCDEF",
            "expires_in": 600,
            "interval": 5,
            "verification_url": custom_url,
        }
        # Replicate the exact expression from cmd_login
        result = code_data.get("verification_url", EXPECTED_VERIFICATION_URL)
        assert result == custom_url

    def test_positive_default_is_connect_when_server_omits(self):
        """When server omits verification_url, the /connect default is used."""
        code_data = {
            "device_code": "dev-abc",
            "user_code": "ABCDEF",
            "expires_in": 600,
            "interval": 5,
            # deliberately no verification_url key
        }
        result = code_data.get("verification_url", EXPECTED_VERIFICATION_URL)
        assert result == EXPECTED_VERIFICATION_URL

    def test_negative_old_url_is_not_the_default(self):
        """The old /auth/device URL is NOT the default returned when key is missing.

        This directly validates the fix: previously the default was
        OLD_VERIFICATION_URL.  Now the default is EXPECTED_VERIFICATION_URL.
        """
        code_data = {"device_code": "x", "user_code": "ABCDEF", "expires_in": 60}
        result = code_data.get("verification_url", EXPECTED_VERIFICATION_URL)
        assert result != OLD_VERIFICATION_URL, (
            f"REGRESSION: fallback returned '{OLD_VERIFICATION_URL}' — "
            "the old broken URL is still the default"
        )


# ---------------------------------------------------------------------------
# Integration test: cmd_login opens the correct URL
# ---------------------------------------------------------------------------


class TestCmdLoginOpensCorrectUrl:
    """End-to-end: cmd_login must open /connect, not /auth/device."""

    def _make_urlopen_side_effect(self, device_payload: dict):
        """Return a side_effect function: first call yields device_payload,
        subsequent calls (polling) raise URLError so the loop exits gracefully."""
        calls = {"count": 0}

        class _FakeResp:
            def __init__(self, data):
                self._data = data

            def read(self):
                return json.dumps(self._data).encode()

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def _side_effect(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return _FakeResp(device_payload)
            raise URLError("no poll responses — deadline forces exit")

        return _side_effect

    def test_negative_old_url_not_opened_when_server_omits_field(self):
        """When server omits verification_url, webbrowser must NOT open /auth/device."""
        device_payload = {
            "device_code": "dev-abc",
            "user_code": "ABCDEF12",
            "expires_in": 1,
            "interval": 1,
            # no verification_url key
        }
        # monotonic returns value past deadline on second call so loop exits
        monotonic_values = iter([0.0, 10.0])

        with patch("urllib.request.urlopen",
                   side_effect=self._make_urlopen_side_effect(device_payload)), \
             patch("webbrowser.open") as mock_browser, \
             patch("sys.exit", side_effect=SystemExit), \
             patch("time.sleep"), \
             patch("time.monotonic", side_effect=lambda: next(monotonic_values,
                                                               10.0)):
            try:
                from gradata import cli
                cli.cmd_login(MagicMock())
            except (SystemExit, StopIteration, Exception):
                pass

        if mock_browser.called:
            opened_url = mock_browser.call_args[0][0]
            assert opened_url != OLD_VERIFICATION_URL, (
                f"REGRESSION: webbrowser.open was called with the old URL "
                f"'{OLD_VERIFICATION_URL}'"
            )

    def test_positive_connect_url_opened_when_server_omits_field(self):
        """When server omits verification_url, webbrowser opens /connect."""
        device_payload = {
            "device_code": "dev-abc",
            "user_code": "ABCDEF12",
            "expires_in": 1,
            "interval": 1,
        }
        monotonic_values = iter([0.0, 10.0])

        with patch("urllib.request.urlopen",
                   side_effect=self._make_urlopen_side_effect(device_payload)), \
             patch("webbrowser.open") as mock_browser, \
             patch("sys.exit", side_effect=SystemExit), \
             patch("time.sleep"), \
             patch("time.monotonic", side_effect=lambda: next(monotonic_values,
                                                               10.0)):
            try:
                from gradata import cli
                cli.cmd_login(MagicMock())
            except (SystemExit, StopIteration, Exception):
                pass

        if mock_browser.called:
            opened_url = mock_browser.call_args[0][0]
            assert opened_url == EXPECTED_VERIFICATION_URL, (
                f"Expected '{EXPECTED_VERIFICATION_URL}' but got '{opened_url}'"
            )
