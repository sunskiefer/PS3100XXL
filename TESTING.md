# Testing PS3100XXL

## Offline (done for 0.1.0)

- `test/run_tests.sh`: the engine under ASan/UBSan (views and navigation, Q-Links following the view, patching,
  unplugging, one cable per input, trigger/voltage check, state save and restore with cables, temperament templates,
  pitch, every waveform, every control swept with a chord held, every one of the 900+ cables patched while playing,
  GEG LED, 48-voice CPU), then the mpc-vst-plugins host test of the whole plugin.
- `tools/check_skin.py`: every control, jack, section and cable picture of the inventory is in the built skin.

## 0.1.3 (offline)

- `test/ui_test.c` (run by `test/run_tests.sh`): the wrapper driven as MPC does: OVERVIEW / < / > are one instance each
  and one press steps one page; a pop-up list opens from its arrow, closes on a pick, on opening another and on a page
  change (and the host is told); six data wheel clicks on CLK 1 RATE step six divisions; a cable from GEG to SG FRQ.
- `tools/check_skin.py`: the header buttons are single instances shown on every section page; no pop-up part is bound to
  the wrapper's `<key>__open` any more.

Found on the Force with 0.1.2 and fixed in 0.1.3: pop-up option text in the framework's pixel font (unreadable); the
data wheel on a pop-up field moved its open flag, not the value; the header buttons were ten copies each, one per page,
swapped under the finger on a press; a pop-up list left open stayed on every other page and took its touches (over the
right half of the patch bay).

## 0.1.5 (checked on a Force, 2026-10-23)

Found on the Force with 0.1.4: taps seemed to do nothing, no ring, no cable, no sound change.
- Device finding (a test counter in the patch_info line, read live from the screen): jack taps DO reach the plugin
  (taps counted on the Force); what failed was showing the result. A tap that only moved engine state never redrew
  the pictures.
- Patching is now a step (`pk`, 7 positions) switched like the overview's page tiles: 1 choose, 2/3 an output waits
  (voltage/trigger), 4/5 an input waits, 6 connected. The jack taps (and CANCEL / UNPLUG / DONE) ask the host to redraw
  (`refresh_display`), as the tiles do. `pk_t` / `pk_c` show the sockets' touch zones and CANCEL.
- The drawn cables stay on the patch panel on steps 1-5 (`cp_`); the overview no longer carries cable copies (`co_`
  and the rings `hd_` / `hi_` stay in params.lock, unused).
- Skin: 4,300 components (it was 6,300 with the overview copies).
- On the Force: tap, tap, CONNECTED page, then the cables on the panel after DONE: works (user, 2026-10-23, 0.1.5 test
  build). Sound check of a patched cable: still to confirm in the table below.
- `test/ui_test.c` and `engine_test`: steps, kinds, either order, one cable per input, unplug, done, cancel.

## 0.1.4 (offline)

Found on the Force with 0.1.3: still no ring or cable in the patch bay; every pop-up list closed as soon as it opened.
- Cables and rings: each picture is now switched by a parameter of at most 10 positions (`cp_` / `co_<out>_<group>`,
  `hd_<group>`, `tools/spec.py`), not one 37-position parameter per output; nothing over 11 positions (the view) has
  been seen working on a Force. `check_skin.py` fails on any switch over 11 positions.
- Pop-up arrows: built like the on/off switches (Mouse Down > Q-Link; the Button flips once). 0.1.3's had a Toggle
  Switch action as well, so a tap flipped the list open and shut. `check_skin.py` fails on an arrow with Toggle Switch.
- The engine closes a list on a pick only when the value really changes (a re-sent value keeps it open).
- Patching in either order (input first, then output), with a ring on a waiting input (`hi_<group>`); a wrong kind
  keeps the first jack waiting.
- `test/ui_test.c`: ring on an output tap, the cable on the patch page and on the overview, unplugging, the 11-position
  limit, a re-sent value.

## On the Force (to do)

| # | Check | Result |
|---|---|---|
| 1 | The plugin loads on a track; how long the screen takes to open | |
| 2 | Overview: every tile opens its section; OVERVIEW and < > work | |
| 3 | Every knob, switch and selector on every section turns and sounds | |
| 4 | Patch bay: tap, tap, CONNECTED page; DONE keeps the cable on the panel | works (2026-10-23) |
| 5 | Tapping a patched output unplugs it; the cable goes | |
| 6 | (dropped in 0.1.5: no cables on the overview tile) | n/a |
| 7 | Q-Links follow the section on screen, names change with it | |
| 8 | PRESET menu lists 16 sounds; a pick changes the sound and keeps the cables | |
| 9 | Save the project, reload: sound, cables and section come back | |
| 10 | CPU with 48 voices and a big chord (`tools/bench.sh`) | |
| 11 | Free memory before and after opening the screen (the skin holds ~6000 cable pieces) | |
| 12 | CLK RATE list readable; arrow opens / closes; a pick closes; page change closes | |
| 13 | Data wheel after tapping a pop-up value steps it | |
| 14 | < and > step one page per press, no flicker | |
