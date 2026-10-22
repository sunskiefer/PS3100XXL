# PS3100XXL inventory

Every control and jack of the instrument, generated from `tools/spec.py` (the build checks the skin against the same list). FB-3100 IDs are the parameter numbers in the Full Bucket FB-3100 1.2 manual.

Left out, and why: the external audio input (an MPC instrument plugin receives no audio), Scala `.scl` import (no file picker on MPC) and FB-3100's program/bank file menu (MPC's PRESET menu and project save cover it).

## Signal Generators

| Control | Key | Range | FB-3100 |
|---|---|---|---|
| Waveform | `sg_wave` | Triangle / Sawtooth / Square / Rectangle / Pulse / PWM | 6 |
| PWM Intensity | `sg_pwm_int` | 0 .. 10 | 7 |
| Fine | `sg_fine` | -50 .. 50 ct | 8 |
| Coarse | `sg_coarse` | -12 .. 12 st | 9 |
| Scale | `sg_octave` | 16' / 8' / 4' / 2' | 10 |
| Freq Mod | `sg_fm_on` | Off / On | 11 |
| Reverse | `sg_fm_rev` | Off / On | 12 |
| MG 1 Intensity | `sg_fm_mg1` | 0 .. 10 | 13 |
| GEG / Ext Intensity | `sg_fm_geg` | 0 .. 10 | 14 |

## Dynamic Lowpass Filter

| Control | Key | Range | FB-3100 |
|---|---|---|---|
| Cutoff | `lp_cutoff` | 0 .. 10 | 17 |
| Peak | `lp_peak` | 0 .. 10 | 18 |
| Kbd Balance | `lp_balance` | -5 .. 5 | 19 |
| Expand | `lp_expand` | 0 .. 10 | 20 |
| Freq Mod | `lp_fm_on` | Off / On | 21 |
| MG 1 Intensity | `lp_fm_mg1` | 0 .. 10 | 22 |
| GEG / Ext Intensity | `lp_fm_geg` | 0 .. 10 | 23 |

## Envelope Modifier

| Control | Key | Range | FB-3100 |
|---|---|---|---|
| Attack | `em_attack` | 0 .. 10 | 25 |
| Decay | `em_decay` | 0 .. 10 | 26 |
| Sustain | `em_sustain` | 0 .. 10 | 27 |
| Release | `em_release` | Damp / Half Damp / Release | 28 |
| Hold | `em_hold` | Off / On | 29 |
| PS-3100 Hold | `ps_hold_mode` | Off / On | 92 |
| Release Override | `rel_override` | Off / On | 93 |
| Release Time | `rel_time` | 0 .. 10 | 94 |
| Velocity | `velocity` | 0 .. 10 | - |

## Resonators

| Control | Key | Range | FB-3100 |
|---|---|---|---|
| Intensity | `res_int` | 0 .. 10 | 32 |
| Freq 1 | `res_f1` | 0 .. 10 | 33 |
| Freq 2 | `res_f2` | 0 .. 10 | 34 |
| Freq 3 | `res_f3` | 0 .. 10 | 35 |
| MG 2 Mod | `res_mg2` | Off / On | 36 |
| Ext Mod | `res_ext` | 0 .. 10 | 37 |

## Total Signal Modifiers

| Control | Key | Range | FB-3100 |
|---|---|---|---|
| Final | `final_vol` | 0 .. 10 | 0 |
| Amp Mod | `amp_mod` | 0 .. 10 | 39 |
| AM by MG 1 | `am_mg1` | Off / On | 40 |
| Ensemble | `ensemble` | Off / On | 41 |
| VCA 1 by GEG | `vca1_geg` | Off / On | 42 |
| VCA 2 by VP 1 | `vca2_vp1` | Off / On | 44 |
| Kbd Balance | `kbd_balance` | -5 .. 5 | 4 |
| Final Pan | `final_pan` | -5 .. 5 | 2 |
| Direct | `direct_vol` | 0 .. 10 | 1 |
| Direct Pan | `direct_pan` | -5 .. 5 | 3 |

## Modulation Generators  /  Sample & Hold

| Control | Key | Range | FB-3100 |
|---|---|---|---|
| MG 1 Wave | `mg1_wave` | Triangle / Saw Down / Saw Up / Square / Pink Noise / White Noise | 46 |
| MG 1 Freq | `mg1_freq` | 0 .. 10 | 47 |
| MG 1 Sync | `mg1_sync` | 17 options | 51 |
| MG Signal | `mg_select` | S/H / MG 1 | 49 |
| MG 2 Freq | `mg2_freq` | 0 .. 10 | 52 |
| MG 2 Sync | `mg2_sync` | 17 options | 53 |
| S/H Clock | `sh_clock` | 0 .. 10 | 54 |
| S/H Synchro | `sh_sync` | Off / On | 55 |
| S/H Host Sync | `sh_host` | 17 options | 57 |

## Gen Envelope  /  Voltage Proc  /  Utilities

| Control | Key | Range | FB-3100 |
|---|---|---|---|
| GEG Trigger | `geg_trigger` | Off / 1 / 2 / 3 / 4 / 5 | 58 |
| Delay | `geg_delay` | 0 .. 10 | 59 |
| Attack | `geg_attack` | 0 .. 10 | 60 |
| Release | `geg_release` | 0 .. 10 | 61 |
| Auto | `geg_auto` | Off / On | 62 |
| Polarity | `geg_polarity` | Positive / Negative | 63 |
| VP 1 Limiter A | `vp1_a` | -5 .. 5 | 65 |
| VP 1 Limiter B | `vp1_b` | -5 .. 5 | 66 |
| VP 2 Limiter A | `vp2_a` | -5 .. 5 | 68 |
| VP 2 Limiter B | `vp2_b` | -5 .. 5 | 69 |
| VP 2 Input | `vp2_src` | VP 2 In / VP 1 | 70 |
| X | `xy_x` | -5 .. 5 | - |
| Y | `xy_y` | -5 .. 5 | - |
| Add Amp | `add_level` | 0 .. 10 | - |
| Manual TRG 1 | `manual_trg1` | push | - |

## Temperament

| Control | Key | Range | FB-3100 |
|---|---|---|---|
| Tune C | `tune_c` | -50 .. 50 ct | 72 |
| Tune C# | `tune_cs` | -50 .. 50 ct | 73 |
| Tune D | `tune_d` | -50 .. 50 ct | 74 |
| Tune D# | `tune_ds` | -50 .. 50 ct | 75 |
| Tune E | `tune_e` | -50 .. 50 ct | 76 |
| Tune F | `tune_f` | -50 .. 50 ct | 77 |
| Tune F# | `tune_fs` | -50 .. 50 ct | 78 |
| Tune G | `tune_g` | -50 .. 50 ct | 79 |
| Tune G# | `tune_gs` | -50 .. 50 ct | 80 |
| Tune A | `tune_a` | -50 .. 50 ct | 81 |
| Tune A# | `tune_as` | -50 .. 50 ct | 82 |
| Tune B | `tune_b` | -50 .. 50 ct | 83 |
| Temperament | `temperament` | 14 options | - |
| Master Tune | `master_tune` | -50 .. 50 ct | - |

## Setup  /  Midi

| Control | Key | Range | FB-3100 |
|---|---|---|---|
| Voices | `voices` | 8 / 12 / 16 / 24 / 32 / 48 | - |
| PB Range | `pb_range` | 0 .. 12 st | 5 |
| CLK 1 Rate | `clk1_rate` | 16 options | 84 |
| CLK 2 Rate | `clk2_rate` | 16 options | 85 |
| TRG 1 CC | `trg1_cc` | 0 .. 127 | 86 |
| TRG 2 CC | `trg2_cc` | 0 .. 127 | 87 |
| VC 1 CC | `vc1_cc` | 0 .. 127 | 88 |
| VC 2 CC | `vc2_cc` | 0 .. 127 | 89 |
| VC 3 CC | `vc3_cc` | 0 .. 127 | 90 |
| VC 4 CC | `vc4_cc` | 0 .. 127 | 91 |

## Patch bay

Each output feeds one input (a junction gives two more copies). An input with no cable uses its default, as on the PS-3100.

### Outputs

| Jack | Type | Signal |
|---|---|---|
| GEG | cv | General envelope, -5..0 or 0..+5 V by polarity |
| GE+ | cv | General envelope, always 0..+5 V |
| MG | cv | MG signal (MG 1 or S/H) through the MG VCA, -5..+5 V |
| MG 1 | cv | MG 1, -5..+5 V |
| MG 2 | cv | MG 2, -5..+5 V |
| S/H | cv | Sample & hold, -5..+5 V |
| VP 1 | cv | Voltage processor 1, between its limiters |
| VP 2 | cv | Voltage processor 2, between its limiters |
| KEY | cv | Last key played, -5..+5 V over the keyboard |
| PB | cv | Pitch bend, -5..+5 V |
| PB+ | cv | Pitch bend, 0..+5 V |
| MW | cv | Mod wheel, -5..+5 V |
| MW+ | cv | Mod wheel, 0..+5 V |
| VC 1 | cv | MIDI CC (Setup), -5..+5 V |
| VC 2 | cv | MIDI CC (Setup), -5..+5 V |
| VC 3 | cv | MIDI CC (Setup), -5..+5 V |
| VC 4 | cv | MIDI CC (Setup), -5..+5 V |
| NOISE | cv | White noise, -5..+5 V |
| +5 V | cv | Constant +5 V |
| -5 V | cv | Constant -5 V |
| X | cv | X-Y manipulator X, -5..+5 V |
| Y | cv | X-Y manipulator Y, -5..+5 V |
| ADD | cv | Add amp: inputs 1-4 summed, times its level |
| J1 A | cv | Junction 1, copy A |
| J1 B | cv | Junction 1, copy B |
| J2 A | cv | Junction 2, copy A |
| J2 B | cv | Junction 2, copy B |
| SNG | trig | Keyboard single trigger (first key) |
| MLT | trig | Keyboard multiple trigger (every key) |
| MG1 CLK | trig | MG 1 clock (each cycle) |
| MG2 CLK | trig | MG 2 clock (each cycle) |
| S/H CLK | trig | S/H clock |
| CLK 1 | trig | Tempo clock 1 (Setup rate) |
| CLK 2 | trig | Tempo clock 2 (Setup rate) |
| TRG 1 | trig | MIDI CC trigger 1 and MANUAL TRG 1 |
| TRG 2 | trig | MIDI CC trigger 2 |

### Inputs

| Jack | Type | Default when unpatched | Destination |
|---|---|---|---|
| SG FRQ | cv | GEG | Signal generator pitch mod (GEG / Ext intensity) |
| SG PWM | cv | MG 2 | Pulse width mod (PWM wave) |
| LP FRQ | cv | GEG | Lowpass cutoff mod (GEG / Ext intensity) |
| EM ATK | cv | - | Envelope modifier attack time |
| RES FRQ | cv | - | Resonator peak frequencies (Ext Mod) |
| VCA 1 | cv | GEG | VCA 1 amplitude (when VCA 1 by GEG is on) |
| VCA 2 | cv | VP 1 | VCA 2 amplitude (when VCA 2 by VP 1 is on) |
| MG AMT | cv | - | MG VCA: amount of the MG signal |
| MG1 FRQ | cv | - | MG 1 frequency |
| S/H IN | cv | MG 1 | Sample & hold input |
| VP1 IN | cv | - | Voltage processor 1 input |
| VP2 IN | cv | - | Voltage processor 2 input |
| ADD 1 | cv | - | Add amp input 1 |
| ADD 2 | cv | - | Add amp input 2 |
| ADD 3 | cv | - | Add amp input 3 |
| ADD 4 | cv | - | Add amp input 4 |
| J1 IN | cv | - | Junction 1 input |
| J2 IN | cv | - | Junction 2 input |
| EM REL | trig | - | Envelope modifier: release every voice |
| GEG TRG | trig | keyboard | General envelope trigger (default: the keyboard) |

89 controls, 36 outputs, 20 inputs.
