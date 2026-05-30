# Briturn — Home Assistant integration

> **This is a maintained fork of [jamesrom/ha-briturn](https://github.com/jamesrom/ha-briturn)
> by [James Romeril](https://github.com/jamesrom).** It was forked to continue
> active development, fix outstanding bugs, and extend support beyond the original
> scope. The original MIT licence is preserved.

Local (LAN-only) Home Assistant integration for **Briturn** Wi-Fi smart bulbs,
which speak the Zengge 2014 protocol (TCP `:5577`). Also works with other bulbs
in the Surplife / Zengge family that respond to the same protocol.

Features:

- On / off
- Brightness
- RGB color
- Color temperature (2700 K – 6500 K, mixed from the bulb's warm-white and cold-white channels)

Communication is direct over your LAN — no cloud, no phone app running.

## Compatibility

Tested against: **Briturn Wi-Fi Smart Bulb** (Amazon AU B0F13RLQRM), model byte `0x35` (RGB+WW+CW).

Likely works with other BL602 / SM2135-based bulbs paired through the Surplife
or Briturn mobile apps, as long as they respond to the Zengge 2014 query on TCP `:5577`.

## Prerequisites

**Pair the bulb to your Wi-Fi first** using the vendor Briturn or Surplife mobile
app. This integration controls an already-paired bulb; it does not do Wi-Fi
provisioning.

Once paired, find the bulb's IP on your network (router admin panel, `arp -a`, etc.).

## Installation

### Via HACS (custom repository)

1. In HACS → **Integrations** → ⋮ → **Custom repositories**.
2. Add `https://github.com/vmlrodrigues/ha-briturn` with category **Integration**.
3. Install **Briturn**, then restart Home Assistant.

### Manual

Copy the `custom_components/briturn/` directory from this repo into your Home
Assistant `config/custom_components/` folder, then restart Home Assistant.

## Configuration

1. **Settings → Devices & Services → Add Integration → Briturn**.
2. Enter the bulb's IP and a friendly name.
3. The integration probes the bulb on TCP `:5577` and creates a light entity.

## How it works

Commands (every frame ends in an 8-bit sum-of-prior-bytes checksum):

| Action | Frame |
|---|---|
| Power on | `71 23 F0` |
| Power off | `71 24 F0` |
| RGB color `(R,G,B)` | `31 R G B 00 00 F0 0F` |
| Warm/cool white `(WW,CW)` | `31 00 00 00 WW CW 0F 0F` |
| Query state | `81 8A 8B` |

The query response is 14 bytes:
`81 model power mode _ _ R G B WW ver CW mode_flag csum` where `mode_flag` is
`0xF0` in RGB mode and `0x0F` in white mode.

## Credits

- [jamesrom/ha-briturn](https://github.com/jamesrom/ha-briturn) — original integration by James Romeril, on which this fork is based.

Protocol reverse-engineering predates this repo by years:

- [vikstrous/zengge-lightcontrol](https://github.com/vikstrous/zengge-lightcontrol) — canonical Zengge 2014 protocol reference.
- [Danielhiversen/flux_led](https://github.com/Danielhiversen/flux_led) — Python implementation that handles many Zengge/Magic Home variants.
- [rdircio/briturnplug](https://github.com/rdircio/briturnplug) — confirmed that Briturn Wi-Fi plugs speak Zengge 2014; pointed the way for the bulb.

## License

[MIT](LICENSE)
