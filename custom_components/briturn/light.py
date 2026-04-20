"""Briturn light entity: on/off, brightness, RGB, and color temperature."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .protocol import (
    async_query_state,
    async_send_cct,
    async_send_power,
    async_send_rgb,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

MIN_KELVIN = 2700
MAX_KELVIN = 6500


def _kelvin_to_ww_cw(kelvin: int, brightness: int) -> tuple[int, int]:
    k = max(MIN_KELVIN, min(MAX_KELVIN, int(kelvin)))
    cool_ratio = (k - MIN_KELVIN) / (MAX_KELVIN - MIN_KELVIN)
    warm_ratio = 1 - cool_ratio
    b = max(0, min(255, int(brightness)))
    return int(round(b * warm_ratio)), int(round(b * cool_ratio))


def _ww_cw_to_kelvin(ww: int, cw: int) -> int:
    total = ww + cw
    if total <= 0:
        return (MIN_KELVIN + MAX_KELVIN) // 2
    cool_ratio = cw / total
    return int(round(MIN_KELVIN + cool_ratio * (MAX_KELVIN - MIN_KELVIN)))


def _scale_rgb(rgb: tuple[int, int, int], brightness: int) -> tuple[int, int, int]:
    b = max(0, min(255, int(brightness))) / 255.0
    return tuple(int(round(max(0, min(255, c)) * b)) for c in rgb)  # type: ignore[return-value]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [BriturnLight(entry.entry_id, data[CONF_HOST], data.get(CONF_NAME) or "Briturn")],
        update_before_add=True,
    )


class BriturnLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP}
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN
    _attr_has_entity_name = False
    _attr_should_poll = True

    def __init__(self, entry_id: str, host: str, name: str) -> None:
        self._host = host
        self._attr_unique_id = f"briturn_{entry_id}"
        self._attr_name = name
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_color_mode = ColorMode.COLOR_TEMP
        self._attr_rgb_color = (255, 255, 255)
        self._attr_color_temp_kelvin = (MIN_KELVIN + MAX_KELVIN) // 2
        self._attr_available = False
        self._unscaled_rgb: tuple[int, int, int] = (255, 255, 255)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=name,
            manufacturer="Briturn",
            model="Zengge 2014 Wi-Fi Bulb",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        brightness = int(kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness or 255))
        rgb = kwargs.get(ATTR_RGB_COLOR)
        kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)

        try:
            if rgb is not None:
                self._unscaled_rgb = tuple(int(c) for c in rgb)  # type: ignore[assignment]
                self._attr_rgb_color = self._unscaled_rgb
                self._attr_color_mode = ColorMode.RGB
                await async_send_rgb(self._host, *_scale_rgb(self._unscaled_rgb, brightness))
            elif kelvin is not None:
                self._attr_color_temp_kelvin = int(kelvin)
                self._attr_color_mode = ColorMode.COLOR_TEMP
                ww, cw = _kelvin_to_ww_cw(self._attr_color_temp_kelvin, brightness)
                await async_send_cct(self._host, ww, cw)
            else:
                # No color specified — re-issue current color at the new brightness.
                if self._attr_color_mode == ColorMode.RGB:
                    await async_send_rgb(self._host, *_scale_rgb(self._unscaled_rgb, brightness))
                else:
                    ww, cw = _kelvin_to_ww_cw(
                        self._attr_color_temp_kelvin or (MIN_KELVIN + MAX_KELVIN) // 2,
                        brightness,
                    )
                    await async_send_cct(self._host, ww, cw)

            await async_send_power(self._host, True)
            self._attr_brightness = brightness
            self._attr_is_on = True
            self._attr_available = True
        except (OSError, TimeoutError) as err:
            _LOGGER.warning("briturn %s turn_on failed: %s", self._host, err)
            self._attr_available = False

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await async_send_power(self._host, False)
            self._attr_is_on = False
            self._attr_available = True
        except (OSError, TimeoutError) as err:
            _LOGGER.warning("briturn %s turn_off failed: %s", self._host, err)
            self._attr_available = False

    async def async_update(self) -> None:
        try:
            state = await async_query_state(self._host)
        except (OSError, TimeoutError) as err:
            _LOGGER.debug("briturn %s poll failed: %s", self._host, err)
            self._attr_available = False
            return

        if state is None:
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_is_on = state.is_on
        if state.brightness:
            self._attr_brightness = state.brightness
        if state.is_rgb_mode:
            self._attr_color_mode = ColorMode.RGB
            self._attr_rgb_color = state.rgb
            if any(state.rgb):
                self._unscaled_rgb = state.rgb
        else:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_color_temp_kelvin = _ww_cw_to_kelvin(state.ww, state.cw)
