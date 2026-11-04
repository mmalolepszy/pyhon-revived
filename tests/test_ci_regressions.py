"""Offline regression tests for the small CI complexity refactors."""

# These tests inject cached state and exercise the private parsing boundaries.
# pylint: disable=protected-access

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock

from pyhon.command_loader import HonCommandLoader
from pyhon.commands import HonCommand
from pyhon.connection.auth import HonAuth
from pyhon.connection.handler.hon import HonConnectionHandler
from pyhon.connection.mqtt import MQTTClient
from pyhon.exceptions import HonAuthenticationError
from pyhon.parameter.enum import HonParameterEnum
from pyhon.parameter.fixed import HonParameterFixed
from pyhon.parameter.program import HonParameterProgram
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


class ParameterContractTests(TestCase):
    def test_numeric_defaults_survive_enum_value_replacement(self):

        for default in (0, 2.5):
            with self.subTest(default=default):
                parameter = HonParameterEnum(
                    "speed", {"defaultValue": default, "enumValues": ["other"]}, ""
                )
                self.assertIn(str(default), parameter.values)
                parameter.values = ["replacement"]
                self.assertIn(str(default), parameter.values)
                parameter.value = default
                self.assertEqual(parameter.value, str(default))
                with self.assertRaises(ValueError):
                    parameter.value = "invalid"

    def test_program_setter_accepts_numeric_category_and_rejects_unknown(self):

        command = SimpleNamespace(category="initial", categories={"2.5": Mock()})
        parameter = HonParameterProgram("program", command, "")
        parameter.value = 2.5
        self.assertEqual(command.category, "2.5")
        with self.assertRaises(ValueError):
            parameter.value = "unknown"

    def test_command_copy_isolates_favourite_parameters(self):

        base = HonCommand("settings", {}, Mock())
        base.parameters["temp"] = HonParameterFixed("temp", {"fixedValue": "20"}, "")
        first, second = base.copy_with_parameters(), base.copy_with_parameters()
        first.parameters["temp"].value = "60"
        first.parameters["extra"] = HonParameterFixed("extra", {}, "")
        self.assertEqual(base.parameters["temp"].value, "20")
        self.assertEqual(second.parameters["temp"].value, "20")
        self.assertNotIn("extra", base.parameters)


class MQTTContractTests(TestCase):
    def setUp(self):

        self.client = MQTTClient(
            SimpleNamespace(api=Mock(), appliances=[Mock()]), "test"
        )

    def test_missing_new_and_rejoined_negotiation_settings(self):
        for settings, expected in [
            (None, False),
            (SimpleNamespace(rejoined_session=False), False),
            (SimpleNamespace(rejoined_session=True), True),
        ]:
            with self.subTest(settings=settings):
                self.client._subscribed = True
                self.client._on_lifecycle_connection_success(
                    SimpleNamespace(negotiated_settings=settings)
                )
                self.assertEqual(self.client._subscribed, expected)

    def test_partial_subscription_failure_can_be_retried(self):
        self.client._subscribe = Mock(side_effect=[RuntimeError("offline"), None])
        with self.assertRaises(RuntimeError):
            self.client._subscribe_appliances()
        self.assertFalse(self.client._subscribed)
        self.client._subscribe_appliances()
        self.assertTrue(self.client._subscribed)


class ResponseLifetimeTests(IsolatedAsyncioTestCase):
    def setUp(self):

        self.handler = HonConnectionHandler(
            "fake@example.invalid", "fake", session=Mock()
        )
        self.handler._auth = SimpleNamespace(
            cognito_token="fake",
            refresh_token="fake",
            id_token="fake",
            token_expires_soon=False,
            token_is_expired=False,
            refresh=AsyncMock(),
        )
        self.handler.create = AsyncMock(return_value=self.handler)
        self.events = []

    def responses(self, statuses, json_error=None):

        responses = list(statuses)

        @asynccontextmanager
        async def request(*_args, **_kwargs):
            status = responses.pop(0)
            self.events.append(("enter", status))
            try:
                yield SimpleNamespace(
                    status=status, json=AsyncMock(side_effect=json_error)
                )
            finally:
                self.events.append(("exit", status))

        return request

    async def test_refresh_relogin_and_response_release_order(self):
        async with self.handler._intercept(
            self.responses([401, 403, 200]), "https://example.invalid"
        ) as response:
            self.assertEqual(response.status, 200)
        self.assertEqual(
            self.events,
            [
                ("enter", 401),
                ("exit", 401),
                ("enter", 403),
                ("exit", 403),
                ("enter", 200),
                ("exit", 200),
            ],
        )
        self.handler.auth.refresh.assert_awaited_once()
        self.handler.create.assert_awaited_once()

    async def test_retries_are_bounded_and_close_final_failed_response(self):
        with self.assertRaises(HonAuthenticationError):
            async with self.handler._intercept(
                self.responses([401, 401, 403]), "https://example.invalid"
            ):
                self.fail("A rejected response must not reach the caller")
        self.assertEqual(self.events[-1], ("exit", 403))
        self.assertEqual(len(self.events), 6)

    async def test_invalid_response_json_closes_response(self):

        error = json.JSONDecodeError("invalid", "", 0)
        with self.assertRaises(HonAuthenticationError):
            async with self.handler._intercept(
                self.responses([200], error), "https://example.invalid"
            ):
                self.fail("Invalid JSON must not reach the caller")
        self.assertEqual(self.events, [("enter", 200), ("exit", 200)])

    async def test_caller_exception_is_preserved_and_response_closed(self):

        error = json.JSONDecodeError("consumer error", "", 0)
        with self.assertRaises(json.JSONDecodeError) as raised:
            async with self.handler._intercept(
                self.responses([200]), "https://example.invalid"
            ):
                raise error
        self.assertIs(raised.exception, error)
        self.assertEqual(self.events[-1], ("exit", 200))

    async def test_cancellation_closes_response(self):

        with self.assertRaises(asyncio.CancelledError):
            async with self.handler._intercept(
                self.responses([200]), "https://example.invalid"
            ):
                raise asyncio.CancelledError
        self.assertEqual(self.events[-1], ("exit", 200))
