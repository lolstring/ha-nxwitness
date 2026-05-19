"""Config flow for NX Witness."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import selector

from .api import (
    NxWitnessApiClient,
    NxWitnessApiError,
    NxWitnessAuthConfig,
    NxWitnessAuthError,
)
from .const import (
    AUTH_MODE_BASIC,
    AUTH_MODE_SESSION,
    CONF_AUTH_MODE,
    CONF_CLIP_FORMAT,
    CONF_CLIP_FPS,
    CONF_CLIP_LOOKBACK_DAYS,
    CONF_DEFAULT_STREAM,
    CONF_DEFAULT_STREAM_FORMAT,
    CONF_DEFAULT_STREAM_RESOLUTION,
    CONF_ENABLE_CAMERAS,
    CONF_ENABLE_CLIPS,
    CONF_ENABLE_MOTION,
    CONF_ENABLED_CAMERA_IDS,
    CONF_MOTION_PERIOD_TYPE,
    CONF_MOTION_WINDOW,
    CONF_SCAN_INTERVAL,
    CONF_USE_HTTPS,
    CONF_VERIFY_SSL,
    DEFAULT_CLIP_FORMAT,
    DEFAULT_CLIP_FPS,
    DEFAULT_CLIP_LOOKBACK_DAYS,
    DEFAULT_ENABLE_CAMERAS,
    DEFAULT_ENABLE_CLIPS,
    DEFAULT_ENABLE_MOTION,
    DEFAULT_MOTION_PERIOD_TYPE,
    DEFAULT_MOTION_WINDOW_SECONDS,
    DEFAULT_PORT_HTTP,
    DEFAULT_PORT_HTTPS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_STREAM,
    DEFAULT_STREAM_FORMAT,
    DEFAULT_STREAM_RESOLUTION,
    DOMAIN,
    MOTION_PERIOD_TYPE_CHOICES,
    STREAM_CHOICES,
    STREAM_FORMAT_CHOICES,
)
from .helpers import _strip_braces, get_device_name, get_enabled_camera_ids


class NxWitnessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an NX Witness config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial connection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                await self._async_validate_input(user_input)
            except NxWitnessAuthError:
                errors["base"] = "invalid_auth"
            except NxWitnessApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"NX Witness {user_input[CONF_HOST]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(user_input),
            errors=errors,
            description_placeholders={
                "read_only_note": (
                    "Use Basic auth to avoid creating a login session "
                    "on the NX server."
                )
            },
        )

    def _build_schema(self, user_input: dict[str, Any] | None) -> vol.Schema:
        defaults = user_input or {}
        use_https = defaults.get(CONF_USE_HTTPS, True)
        default_port = DEFAULT_PORT_HTTPS if use_https else DEFAULT_PORT_HTTP
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
                vol.Required(
                    CONF_PORT, default=defaults.get(CONF_PORT, default_port)
                ): int,
                vol.Required(CONF_USE_HTTPS, default=use_https): bool,
                vol.Required(
                    CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, False)
                ): bool,
                vol.Required(
                    CONF_AUTH_MODE,
                    default=defaults.get(CONF_AUTH_MODE, AUTH_MODE_BASIC),
                ): vol.In(
                    {
                        AUTH_MODE_BASIC: "Basic (read-only preferred)",
                        AUTH_MODE_SESSION: "Session token",
                    }
                ),
                vol.Required(
                    CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
                ): str,
                vol.Required(
                    CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")
                ): str,
                vol.Required(
                    CONF_MOTION_WINDOW,
                    default=defaults.get(
                        CONF_MOTION_WINDOW, DEFAULT_MOTION_WINDOW_SECONDS
                    ),
                ): int,
            }
        )

    async def _async_validate_input(self, user_input: dict[str, Any]) -> None:
        session = async_create_clientsession(
            self.hass, verify_ssl=user_input[CONF_VERIFY_SSL]
        )
        client = NxWitnessApiClient(
            session,
            NxWitnessAuthConfig(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                use_https=user_input[CONF_USE_HTTPS],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                auth_mode=user_input[CONF_AUTH_MODE],
                verify_ssl=user_input[CONF_VERIFY_SSL],
            ),
        )
        await client.async_validate_connection()

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NxWitnessOptionsFlow:
        """Return the options flow handler."""
        return NxWitnessOptionsFlow()


class NxWitnessOptionsFlow(config_entries.OptionsFlow):
    """Handle NX Witness options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {**self.config_entry.data, **self.config_entry.options}
        runtime = getattr(self.config_entry, "runtime_data", None)
        devices = (
            (runtime.coordinator.data or {}).get("devices", []) if runtime else []
        )
        enabled_camera_ids = sorted(get_enabled_camera_ids(options, devices))
        camera_options = [
            {
                "label": get_device_name(device),
                "value": str(device["id"]),
            }
            for device in devices
            if device.get("id")
        ]
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_CAMERAS,
                        default=options.get(
                            CONF_ENABLE_CAMERAS, DEFAULT_ENABLE_CAMERAS
                        ),
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_MOTION,
                        default=options.get(CONF_ENABLE_MOTION, DEFAULT_ENABLE_MOTION),
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_CLIPS,
                        default=options.get(CONF_ENABLE_CLIPS, DEFAULT_ENABLE_CLIPS),
                    ): bool,
                    vol.Optional(
                        CONF_ENABLED_CAMERA_IDS,
                        default=[
                            _strip_braces(str(id_))
                            for id_ in options.get(
                                CONF_ENABLED_CAMERA_IDS, enabled_camera_ids
                            )
                            if id_ not in (None, "")
                        ],
                    ): selector(
                        {
                            "select": {
                                "options": camera_options,
                                "multiple": True,
                                "mode": "dropdown",
                            }
                        }
                    ),
                    vol.Required(
                        CONF_MOTION_WINDOW,
                        default=options.get(
                            CONF_MOTION_WINDOW, DEFAULT_MOTION_WINDOW_SECONDS
                        ),
                    ): selector(
                        {
                            "number": {
                                "min": 5,
                                "max": 3600,
                                "mode": "box",
                                "unit_of_measurement": "s",
                            }
                        }
                    ),
                    vol.Required(
                        CONF_MOTION_PERIOD_TYPE,
                        default=options.get(
                            CONF_MOTION_PERIOD_TYPE, DEFAULT_MOTION_PERIOD_TYPE
                        ),
                    ): vol.In(MOTION_PERIOD_TYPE_CHOICES),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
                        ),
                    ): selector(
                        {
                            "number": {
                                "min": 5,
                                "max": 300,
                                "mode": "box",
                                "unit_of_measurement": "s",
                            }
                        }
                    ),
                    vol.Required(
                        CONF_DEFAULT_STREAM,
                        default=options.get(CONF_DEFAULT_STREAM, DEFAULT_STREAM),
                    ): vol.In(STREAM_CHOICES),
                    vol.Required(
                        CONF_DEFAULT_STREAM_FORMAT,
                        default=options.get(
                            CONF_DEFAULT_STREAM_FORMAT, DEFAULT_STREAM_FORMAT
                        ),
                    ): vol.In(STREAM_FORMAT_CHOICES),
                    vol.Required(
                        CONF_DEFAULT_STREAM_RESOLUTION,
                        default=options.get(
                            CONF_DEFAULT_STREAM_RESOLUTION, DEFAULT_STREAM_RESOLUTION
                        ),
                    ): str,
                    vol.Required(
                        CONF_CLIP_FORMAT,
                        default=options.get(CONF_CLIP_FORMAT, DEFAULT_CLIP_FORMAT),
                    ): vol.In(STREAM_FORMAT_CHOICES),
                    vol.Required(
                        CONF_CLIP_FPS,
                        default=options.get(CONF_CLIP_FPS, DEFAULT_CLIP_FPS),
                    ): selector(
                        {
                            "number": {
                                "min": 1,
                                "max": 60,
                                "mode": "box",
                                "unit_of_measurement": "fps",
                            }
                        }
                    ),
                    vol.Required(
                        CONF_CLIP_LOOKBACK_DAYS,
                        default=options.get(
                            CONF_CLIP_LOOKBACK_DAYS, DEFAULT_CLIP_LOOKBACK_DAYS
                        ),
                    ): selector(
                        {
                            "number": {
                                "min": 1,
                                "max": 90,
                                "mode": "box",
                                "unit_of_measurement": "days",
                            }
                        }
                    ),
                }
            ),
        )
