"""Zengge 2014 protocol frames for Briturn bulbs (TCP :5577).

Reference: vikstrous/zengge-lightcontrol and Danielhiversen/flux_led.
Every frame ends in an 8-bit sum-of-prior-bytes checksum.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

MASK_RGB_ONLY = 0xF0
MASK_WHITE_ONLY = 0x0F
MODE_FLAG_RGB = 0xF0
MODE_FLAG_WHITE = 0x0F
PERSIST = 0x0F


def _csum(data: bytes) -> int:
    return sum(data) & 0xFF


def _frame(*parts: int) -> bytes:
    body = bytes(parts)
    return body + bytes([_csum(body)])


def power_frame(on: bool) -> bytes:
    return _frame(0x71, 0x23 if on else 0x24, 0xF0)


def query_frame() -> bytes:
    return _frame(0x81, 0x8A, 0x8B)


def rgb_frame(r: int, g: int, b: int) -> bytes:
    r, g, b = (max(0, min(255, int(v))) for v in (r, g, b))
    return _frame(0x31, r, g, b, 0x00, 0x00, MASK_RGB_ONLY, PERSIST)


def cct_frame(ww: int, cw: int) -> bytes:
    ww = max(0, min(255, int(ww)))
    cw = max(0, min(255, int(cw)))
    return _frame(0x31, 0x00, 0x00, 0x00, ww, cw, MASK_WHITE_ONLY, PERSIST)


def brightness_frame(level_0_255: int) -> bytes:
    """Back-compat: warm-white-only brightness."""
    return cct_frame(level_0_255, 0)


@dataclass(frozen=True)
class BulbState:
    is_on: bool
    brightness: int  # 0..255, visual brightness proxy
    is_rgb_mode: bool
    rgb: tuple[int, int, int]
    ww: int
    cw: int


def parse_state(resp: bytes) -> BulbState | None:
    """Parse a 14-byte response to the 0x81/0x8A/0x8B query.

    Layout: [0]=0x81 [1]=model [2]=power(0x23/0x24) [3..5]=mode/speed
            [6]=R [7]=G [8]=B [9]=WW [10]=ver [11]=CW [12]=mode_flag [13]=csum
    """
    if len(resp) < 14 or resp[0] != 0x81:
        return None
    is_on = resp[2] == 0x23
    r, g, b = resp[6], resp[7], resp[8]
    ww, cw = resp[9], resp[11]
    is_rgb_mode = resp[12] == MODE_FLAG_RGB
    if is_rgb_mode:
        brightness = max(r, g, b)
    else:
        brightness = max(ww, cw)
    if is_on and brightness == 0:
        brightness = 255
    return BulbState(
        is_on=is_on,
        brightness=brightness,
        is_rgb_mode=is_rgb_mode,
        rgb=(r, g, b),
        ww=ww,
        cw=cw,
    )


async def _rw(host: str, port: int, payload: bytes, read_bytes: int, timeout: float) -> bytes:
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=timeout
    )
    try:
        writer.write(payload)
        await writer.drain()
        if read_bytes <= 0:
            return b""
        try:
            return await asyncio.wait_for(reader.readexactly(read_bytes), timeout=timeout)
        except asyncio.IncompleteReadError as err:
            return err.partial
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


async def async_send_power(host: str, on: bool, port: int = 5577, timeout: float = 3.0) -> None:
    await _rw(host, port, power_frame(on), 0, timeout)


async def async_send_rgb(host: str, r: int, g: int, b: int, port: int = 5577, timeout: float = 3.0) -> None:
    await _rw(host, port, rgb_frame(r, g, b), 0, timeout)


async def async_send_cct(host: str, ww: int, cw: int, port: int = 5577, timeout: float = 3.0) -> None:
    await _rw(host, port, cct_frame(ww, cw), 0, timeout)


async def async_send_brightness(host: str, level: int, port: int = 5577, timeout: float = 3.0) -> None:
    await _rw(host, port, brightness_frame(level), 0, timeout)


async def async_query_state(host: str, port: int = 5577, timeout: float = 3.0) -> BulbState | None:
    resp = await _rw(host, port, query_frame(), 14, timeout)
    return parse_state(resp)
