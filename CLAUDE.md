# CLAUDE.md

## Project overview

Home Assistant custom integration for Briturn Wi-Fi smart bulbs and compatible Zengge/Surplife devices. Controls bulbs locally over LAN via the Zengge 2014 protocol on TCP port 5577. No cloud dependency.

## Repository structure

```
custom_components/briturn/
├── __init__.py        # Entry point; platform setup/teardown
├── const.py           # Domain, config keys, port
├── config_flow.py     # UI config flow (host + name)
├── manifest.json      # HA integration metadata
├── strings.json       # UI strings
├── light.py           # Light entity (on/off, brightness, RGB, CCT)
├── protocol.py        # Zengge 2014 protocol: frame builders + async I/O
└── translations/en.json
```

## Protocol notes (Zengge 2014)

- TCP port 5577, one command per connection
- Every frame ends with an 8-bit sum-of-prior-bytes checksum
- Key command bytes: `0x31` = set channels, `0x71` = power on/off, `0x81/0x8A/0x8B` = query state
- Query response is 14 bytes: `[0]=0x81 [1]=model [2]=power [3..5]=mode/speed [6]=R [7]=G [8]=B [9]=WW [10]=ver [11]=CW [12]=mode_flag [13]=csum`
- `mode_flag 0xF0` = RGB mode, `0x0F` = white/CCT mode

## Known bulb behaviour (Briturn RGBWW, model byte 0x35)

- **Warm-white only in practice**: the CW channel is always 0 in query responses on tested hardware; all brightness goes through the WW channel.
- **Built-in fade effect**: the bulb has a hardware fade transition. Large brightness changes (e.g. 10% → 100%) can take up to ~28 seconds to complete. Query responses during the fade return intermediate values, not the commanded value.
- **Slow command application**: the bulb takes ~200–300 ms to apply a change after receiving the TCP frame.

## Key design decisions

- **Fade guard in `async_update`**: HA calls `async_update` immediately after every service call. Because the bulb fades slowly, polls during the fade return intermediate values that would overwrite the correct commanded state. The guard skips brightness/colour updates from polls until `SCAN_INTERVAL` (30 s) has elapsed with no new commands — by which point the fade is always complete.
- **Conditional power command**: `async_send_power(True)` is only sent in `async_turn_on` when the bulb is actually off (`not self._attr_is_on`). Sending power-on to an already-on bulb resets it to a factory default dim state.
- **`ww + cw` for brightness read-back**: in CCT mode, `brightness = min(255, ww + cw)` rather than `max(ww, cw)`, since the commanded brightness is distributed proportionally across both channels.

## Commit guidelines

Do not commit or push unless explicitly instructed to by the developer. All code changes must be reviewed before committing.

Commit message format:

```
<type>: <short summary in present tense, under 72 chars>

<optional body — explain WHY, not what. Wrap at 72 chars.>
```

Types: `fix`, `feat`, `refactor`, `docs`, `chore`.

Examples:
```
fix: skip brightness update during bulb fade transition

feat: add RGB colour mode support

docs: update README with fork attribution
```
