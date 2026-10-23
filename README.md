# PS3100XXL v0.1.5

**A Korg PS-3100-style semi-modular polyphonic synthesizer for MPC OS on the Akai Force, with the whole panel on one
zoomable page and a patch bay you patch by touch.**

PS3100XXL is a VST2 instrument for MPC OS's built-in plugin host, made by L'Cronx. It follows the 1977 Korg PS-3100:
one oscillator, filter and envelope per key (up to 48 voices), the three-peak resonators, the ensemble, two
modulation generators, sample & hold, the general envelope, the voltage processors, the twelve temperament knobs and
the patch panel. The sound engine is its own, written from the PS-3100's published architecture and the Full Bucket
FB-3100 manual's description of it; no code from either.

> [!NOTE]
> **Status: 0.1.5.** Patching works on the Force (checked 2026-10-23 on a Force). 0.1.2 to 0.1.4 drew no cable and made
> no connection there. What changed: a jack tap now opens a *step* (a page switch, the same mechanism as the overview's
> tiles, which was the one thing known to work), the waiting jack's kind decides which sockets stay lit, and a finished
> cable has its own page; the drawn cables then stay on the patch panel. The skin dropped the overview's cable copies and
> the held-jack rings. Passes its engine, host and UI tests on x86 under ASan and UBSan.

![Overview](docs/img/overview.png)

## How it works on the screen

- **Overview:** the whole panel on one page. Each section is a tile showing its controls in miniature, and the patch
  bay shows its sockets. **Tap a tile to zoom into that section.**
- **Zoomed in:** the section fills the screen with large controls. **OVERVIEW** goes back; **<** and **>** step to the
  neighbouring section.
- **Patch bay:** tap a socket (an output or an input, in either order). The sockets that can take the other end of
  the cable stay lit with an orange ring, the others dim; tap the other end and the **CONNECTED** page shows the cable
  between the two jacks' names. **DONE** keeps it, **UNPLUG** removes it, **CANCEL** (top right) drops a half-made
  patch. A voltage output only joins a voltage input, a trigger only a trigger. One cable per output and per input, as
  on the PS-3100: a new cable into an input replaces the old one. Tapping a patched socket opens its cable's page.
- **Pop-up lists** (CLK RATE, MG SYNC, S/H HOST SYNC, TEMPERAMENT): tap the **arrow box** on the right of the field to
  open or close the list, then tap an option. Tap the value itself to put it on the data wheel and a Q-Link. A list
  closes when you pick, open another list, or change page.
- **Q-Links:** the 16 Q-Links follow the section on screen (on the overview: the main sound controls).
- **Presets:** 16 factory sounds in MPC's PRESET menu. A preset changes the controls and keeps your patch.

![Patch bay](docs/img/patch.png)

## Sections

Signal generators (6 waves, 16'-2', fine/coarse, MG 1 and GEG frequency mod with reverse), dynamic lowpass (cutoff,
peak, keyboard balance, expand, mod), envelope modifier (ADS, damp / half damp / release, hold, PS-3100 hold mode,
release override, velocity), resonators (intensity, 3 peaks, MG 2 mod, ext mod), total signal modifiers (amp mod:
cross to ring, ensemble, VCA 1 by GEG, VCA 2 by VP 1, keyboard balance, final and direct with pan), MG 1 (6 waves),
MG 2, S/H (with tempo sync), general envelope (trigger by 1-5 keys, delay, attack, release, auto, polarity, LED), two
voltage processors, X-Y, add amp, manual trigger, temperament (12 knobs + 14 historical templates + master tune),
setup (voices 8-48, pitch bend range, two tempo clocks, MIDI CC triggers and VC 1-4).

Patch bay: 36 outputs (GEG, GE+, MG, MG 1, MG 2, S/H, VP 1, VP 2, noise, key, pitch bend, mod wheel, VC 1-4, +5 V,
-5 V, X, Y, add amp, two junctions with two copies each, and 9 triggers) and 20 inputs. The full list with ranges and
defaults is in [docs/INVENTORY.md](docs/INVENTORY.md), generated from the same file the build checks the skin against.

Left out: the external audio input (an MPC instrument plugin gets no audio input) and Scala file import (no file
picker on MPC).

## Install

Download the zip from Releases and follow its `INSTALL.md` (the installer stops and restarts MPC).

## Build

`./build.sh` (Python 3 with Pillow, a host gcc, Zig: `pip install ziglang`). `test/run_tests.sh` runs the tests.
Everything about the instrument's controls, jacks and views lives in `tools/spec.py`; `tools/gen_params.py` writes the
parameter list, layout and inventory from it, `tools/post_skin.py` draws the panel, knobs, jacks and cables, and
`tools/check_skin.py` fails the build if anything in the inventory is missing from the skin.

Built on [mpc-vst-plugins](https://github.com/sd88me/mpc-vst-plugins). Licence: GPL-3.0-or-later.
Korg and PS-3100 are trademarks of their owners; PS3100XXL is not affiliated with Korg or Full Bucket Music.
