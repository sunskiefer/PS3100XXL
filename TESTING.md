# Testing PS3100XXL

## Offline (done for 0.1.0)

- `test/run_tests.sh`: the engine under ASan/UBSan (views and navigation, Q-Links following the view, patching,
  unplugging, one cable per input, trigger/voltage check, state save and restore with cables, temperament templates,
  pitch, every waveform, every control swept with a chord held, every one of the 900+ cables patched while playing,
  GEG LED, 48-voice CPU), then the mpc-vst-plugins host test of the whole plugin.
- `tools/check_skin.py`: every control, jack, section and cable picture of the inventory is in the built skin.

## On the Force (to do)

| # | Check | Result |
|---|---|---|
| 1 | The plugin loads on a track; how long the screen takes to open | |
| 2 | Overview: every tile opens its section; OVERVIEW and < > work | |
| 3 | Every knob, switch and selector on every section turns and sounds | |
| 4 | Patch bay: output tap shows the ring, input tap draws the cable | |
| 5 | Tapping a patched output unplugs it; the cable goes | |
| 6 | Cables also show on the overview's patch bay tile | |
| 7 | Q-Links follow the section on screen, names change with it | |
| 8 | PRESET menu lists 16 sounds; a pick changes the sound and keeps the cables | |
| 9 | Save the project, reload: sound, cables and section come back | |
| 10 | CPU with 48 voices and a big chord (`tools/bench.sh`) | |
| 11 | Free memory before and after opening the screen (the skin holds ~6000 cable pieces) | |
