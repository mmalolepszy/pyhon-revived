"""Offline regression tests for the small CI complexity refactors."""

# These tests inject cached state and exercise the private parsing boundaries.
# pylint: disable=protected-access

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock

from pyhon.command_loader import HonCommandLoader
from pyhon.connection.auth import HonAuth
from pyhon.exceptions import HonAuthenticationError
from pyhon.parameter.fixed import HonParameterFixed
from pyhon.rules import HonRuleSet


class FavouriteTests(TestCase):
    def test_nested_values_then_flat_overrides_and_unknown_keys(self):
        parameter = HonParameterFixed("temp", {"fixedValue": "20"}, "parameters")
        command = SimpleNamespace(parameters={"temp": parameter})
        loader = HonCommandLoader(Mock(), Mock())
        loader._update_base_command_with_data(
            command,
            {
                "name": "Favourite",
                "command": {
                    "parameters": {"temp": "40", "unknown": "1"},
                    "temp": "60",
                },
            },
        )
        self.assertEqual(parameter.value, "60")


class RuleTests(TestCase):
    def test_scalar_multi_value_and_nested_conditions(self):
        command = SimpleNamespace(appliance=SimpleNamespace(options={}))
        rules = HonRuleSet(
            command,
            {
                "temp": {
                    "@mode": {"1|2": "40", "3": {"@door": {"0": "60"}}},
                    "@bad": "unsupported",
                }
            },
        ).rules
        self.assertEqual([rule.trigger_value for rule in rules["mode"]], ["1", "2"])
        self.assertEqual(rules["mode"][0].param_data["fixedValue"], "40")
        self.assertEqual(rules["door"][0].extras, {"mode": "3"})
        self.assertNotIn("bad", rules)


class RefreshTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.auth = HonAuth(Mock(), "fake@example.invalid", "fake", Mock())
        self.auth._session_id = "session"
        self.auth._code_verifier = "verifier"
        self.auth._get_tokens = AsyncMock(return_value=True)
        self.auth.authenticate = AsyncMock()

    async def test_cached_session_avoids_credentials_login(self):
        self.assertTrue(await self.auth.refresh("refresh-token"))
        self.assertEqual(self.auth.refresh_token, "refresh-token")
        self.auth.authenticate.assert_not_awaited()

    async def test_expired_session_falls_back_to_credentials(self):
        self.auth._get_tokens.side_effect = HonAuthenticationError()
        self.assertTrue(await self.auth.refresh())
        self.auth.authenticate.assert_awaited_once()

    async def test_missing_session_and_rejected_login_return_false(self):
        self.auth._session_id = ""
        self.auth.authenticate.side_effect = HonAuthenticationError()
        self.assertFalse(await self.auth.refresh())
        self.auth._get_tokens.assert_not_awaited()

    async def test_transport_failure_propagates_without_credentials_retry(self):
        self.auth._get_tokens.side_effect = OSError("offline")
        with self.assertRaises(OSError):
            await self.auth.refresh()
        self.auth.authenticate.assert_not_awaited()
