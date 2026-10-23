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

## On the Force (to do)

| # | Check | Result |
|---|---|---|
| 1 | The plugin loads on a track; how long the screen takes to open | |
| 2 | Overview: every tile opens its section; OVERVIEW and < > work | |
| 3 | Every knob, switch and selector on every section turns and sounds | |
| 4 | Patch bay: output tap shows the ring, input tap draws the cable (0.1.2: nothing happened) | |
| 5 | Tapping a patched output unplugs it; the cable goes | |
| 6 | Cables also show on the overview's patch bay tile | |
| 7 | Q-Links follow the section on screen, names change with it | |
| 8 | PRESET menu lists 16 sounds; a pick changes the sound and keeps the cables | |
| 9 | Save the project, reload: sound, cables and section come back | |
| 10 | CPU with 48 voices and a big chord (`tools/bench.sh`) | |
| 11 | Free memory before and after opening the screen (the skin holds ~6000 cable pieces) | |
| 12 | CLK RATE list readable; arrow opens / closes; a pick closes; page change closes | |
| 13 | Data wheel after tapping a pop-up value steps it | |
| 14 | < and > step one page per press, no flicker | |
