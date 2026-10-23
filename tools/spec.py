"""PS3100XXL: the one source of truth for every control, jack, view and position.

Everything else is generated from this file:
  tools/gen_params.py  -> params.json, src/param_ids.h, layout.conf, docs/INVENTORY.md
  tools/post_skin.py   -> panel art, knob strips, jacks, cables, overview (reads the built skin + this file)

MPC stores automation and saved values by parameter INDEX, so once a version ships, the parameter list below is
append-only: never reorder, rename a key or remove a parameter.

Coordinates are skin pixels: the plugin page is 1280 x 628 (layout.conf adds 86 to y, the Force Shadow offset).

Inventory sources: the Full Bucket FB-3100 1.2 manual (parameter IDs 0-95 in brackets) and the Korg PS-3100 itself;
extras from the CHORG panel (junctions, add amp, X-Y, +5/-5 V). Nothing from the PS-3100 / FB-3100 is left out except
the external audio input (an MPC instrument plugin gets no audio input), Scala file import (no file picker on MPC)
and FB-3100's own program/bank file menu (MPC's PRESET menu and project save do that job here).
"""

# ---------------------------------------------------------------------------------------------- shared option lists
OFF_ON = ["Off", "On"]
DIVS = ["8 Bars", "4 Bars", "2 Bars", "1 Bar", "1/2", "1/4", "1/8", "1/16", "1/32",
        "1/2 T", "1/4 T", "1/8 T", "1/16 T", "1/2 .", "1/4 .", "1/8 ."]
DIV_BEATS = [32, 16, 8, 4, 2, 1, 0.5, 0.25, 0.125, 4 / 3.0, 2 / 3.0, 1 / 3.0, 1 / 6.0, 3, 1.5, 0.75]
SYNC = ["Free"] + DIVS
TEMPERAMENTS = ["Equal", "Pythagorean", "Just", "Meantone 1/3", "Meantone 2/7", "Meantone 1/4", "Meantone 1/5",
                "Meantone 1/6", "Werckmeister III", "Kirnberger II", "Kirnberger III", "Vallotti", "Young II", "Kellner"]
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# ---------------------------------------------------------------------------------------------------------- views
# (key, title on the zoomed page, title on the overview tile)
VIEWS = [
    ("overview", "PS3100XXL", ""),
    ("sg", "SIGNAL GENERATORS", "SIGNAL GEN"),
    ("lp", "DYNAMIC LOWPASS FILTER", "LOWPASS"),
    ("em", "ENVELOPE MODIFIER", "ENVELOPE"),
    ("res", "RESONATORS", "RESONATORS"),
    ("tm", "TOTAL SIGNAL MODIFIERS", "TOTAL MODIFIERS"),
    ("mod", "MODULATION GENERATORS  /  SAMPLE & HOLD", "MG / S&H"),
    ("geg", "GEN ENVELOPE  /  VOLTAGE PROC  /  UTILITIES", "GEN ENV / VP"),
    ("tun", "TEMPERAMENT", "TEMPERAMENT"),
    ("patch", "PATCH BAY", "PATCH BAY"),
    ("setup", "SETUP  /  MIDI", "SETUP"),
]
VIEW_KEYS = [v[0] for v in VIEWS]
# Overview tiles (x, y, w, h) on the 1280 x 628 page: each shows its zoomed page in miniature (same 2.04 aspect), the
# signal path along the top row, modulation and setup below, the patch bay large at the bottom with its live cables.
TILES = {}
_TW, _TH, _GAP = 250, 123, 6
for _i, _k in enumerate(["sg", "lp", "em", "res", "tm"]):
    TILES[_k] = (5 + _i * (_TW + _GAP), 74, _TW, _TH)
for _i, _k in enumerate(["mod", "geg", "tun", "setup"]):
    TILES[_k] = (5 + _i * (_TW + _GAP), 74 + _TH + _GAP, _TW, _TH)
TILES["patch"] = (5, 74 + 2 * (_TH + _GAP), 556, 273)   # the patch bay, big: its cables are the point

# --------------------------------------------------------------------------------------------------- the controls
# Each control: dict(key, name, kind, ...). kind: knob (min, max, default, r), toggle (default), enum (options,
# default, widget: enum_h / popup, sw, sh, rows), button (momentary). view + cx, cy place it on its zoomed page.
# fb = the FB-3100 parameter ID it stands for (None: PS3100XXL's own).
BIG, SMALL = 58, 46          # knob radii: the PS-3100's big and small knobs (58 is the filmstrip limit, NOTES)


def K(key, name, lo, hi, de, view, cx, cy, r=SMALL, fb=None, unit="", intd=False):
    return dict(key=key, name=name, kind="knob", min=lo, max=hi, default=de, view=view, cx=cx, cy=cy, r=r, fb=fb,
                unit=unit, int=intd)


def T(key, name, de, view, cx, cy, fb=None, options=OFF_ON):
    return dict(key=key, name=name, kind="toggle", options=options, default=de, view=view, cx=cx, cy=cy, fb=fb)


def E(key, name, options, de, view, cx, cy, fb=None, widget="enum_h", sw=150, sh=56, rows=1, w=240, h=56):
    return dict(key=key, name=name, kind="enum", options=options, default=de, view=view, cx=cx, cy=cy, fb=fb,
                widget=widget, sw=sw, sh=sh, rows=rows, w=w, h=h)


def B(key, name, view, cx, cy, fb=None):
    return dict(key=key, name=name, kind="button", view=view, cx=cx, cy=cy, fb=fb)


R1, R2, R3 = 215, 420, 560   # content rows on a zoomed page (below the 70 px header)

CONTROLS = [
    # parameter 0 first: MPC's host toggles parameter 0 on insert and on every STOP, and the wrapper holds its writes
    # (mpc-vst-plugins NOTES 2026-10-10), so it is a plain level knob here, as on the FB-3100 (ID 0), never a selector
    K("final_vol", "Final", 0, 10, 7, "tm", 720, 200, r=BIG, fb=0),
    # ---- SIGNAL GENERATORS [6-14]
    E("sg_wave", "Waveform", ["Triangle", "Sawtooth", "Square", "Rectangle", "Pulse", "PWM"], 1, "sg", 250, 190,
      fb=6, sw=150, sh=60, rows=2),
    K("sg_pwm_int", "PWM Intensity", 0, 10, 5, "sg", 560, 190, fb=7),
    K("sg_fine", "Fine", -50, 50, 0, "sg", 760, 190, fb=8, unit="ct", intd=True),
    K("sg_coarse", "Coarse", -12, 12, 0, "sg", 960, 190, fb=9, unit="st", intd=True),
    E("sg_octave", "Scale", ["16'", "8'", "4'", "2'"], 1, "sg", 250, 420, fb=10, sw=110, sh=60),
    T("sg_fm_on", "Freq Mod", 0, "sg", 560, 420, fb=11),
    T("sg_fm_rev", "Reverse", 0, "sg", 560, 540, fb=12),
    K("sg_fm_mg1", "MG 1 Intensity", 0, 10, 0, "sg", 760, 430, r=BIG, fb=13),
    K("sg_fm_geg", "GEG / Ext Intensity", 0, 10, 0, "sg", 960, 430, r=BIG, fb=14),
    # ---- DYNAMIC LOWPASS FILTER [17-23]
    K("lp_cutoff", "Cutoff", 0, 10, 6, "lp", 200, 200, r=BIG, fb=17),
    K("lp_peak", "Peak", 0, 10, 2, "lp", 420, 200, r=BIG, fb=18),
    K("lp_balance", "Kbd Balance", -5, 5, 0, "lp", 640, 200, fb=19),
    K("lp_expand", "Expand", 0, 10, 5, "lp", 860, 200, fb=20),
    T("lp_fm_on", "Freq Mod", 1, "lp", 200, 440, fb=21),
    K("lp_fm_mg1", "MG 1 Intensity", 0, 10, 0, "lp", 420, 440, r=BIG, fb=22),
    K("lp_fm_geg", "GEG / Ext Intensity", 0, 10, 0, "lp", 640, 440, r=BIG, fb=23),
    # ---- ENVELOPE MODIFIER [25-29] + tweaks [92-94]
    K("em_attack", "Attack", 0, 10, 0.5, "em", 180, 200, r=BIG, fb=25),
    K("em_decay", "Decay", 0, 10, 5, "em", 400, 200, r=BIG, fb=26),
    K("em_sustain", "Sustain", 0, 10, 7, "em", 620, 200, r=BIG, fb=27),
    E("em_release", "Release", ["Damp", "Half Damp", "Release"], 2, "em", 950, 200, fb=28, sw=140, sh=60),
    T("em_hold", "Hold", 0, "em", 180, 450, fb=29),
    T("ps_hold_mode", "PS-3100 Hold", 0, "em", 400, 450, fb=92),
    T("rel_override", "Release Override", 0, "em", 620, 450, fb=93),
    K("rel_time", "Release Time", 0, 10, 5, "em", 840, 450, fb=94),
    K("velocity", "Velocity", 0, 10, 0, "em", 1060, 450),
    # ---- RESONATORS [32-37]
    K("res_int", "Intensity", 0, 10, 0, "res", 200, 200, r=BIG, fb=32),
    K("res_f1", "Freq 1", 0, 10, 3, "res", 420, 200, fb=33),
    K("res_f2", "Freq 2", 0, 10, 5, "res", 640, 200, fb=34),
    K("res_f3", "Freq 3", 0, 10, 7, "res", 860, 200, fb=35),
    T("res_mg2", "MG 2 Mod", 0, "res", 420, 450, fb=36),
    K("res_ext", "Ext Mod", 0, 10, 0, "res", 640, 450, fb=37),
    # ---- TOTAL SIGNAL MODIFIERS [39-44] + global [0-5]
    K("amp_mod", "Amp Mod", 0, 10, 5, "tm", 140, 200, fb=39),
    T("am_mg1", "AM by MG 1", 0, "tm", 140, 440, fb=40),
    T("ensemble", "Ensemble", 1, "tm", 330, 200, fb=41),
    T("vca1_geg", "VCA 1 by GEG", 0, "tm", 330, 440, fb=42),
    T("vca2_vp1", "VCA 2 by VP 1", 0, "tm", 520, 440, fb=44),
    K("kbd_balance", "Kbd Balance", -5, 5, 0, "tm", 520, 200, fb=4),
    K("final_pan", "Final Pan", -5, 5, 0, "tm", 920, 200, fb=2),
    K("direct_vol", "Direct", 0, 10, 0, "tm", 720, 440, r=BIG, fb=1),
    K("direct_pan", "Direct Pan", -5, 5, 0, "tm", 920, 440, fb=3),
    # ---- MODULATION GENERATORS, S/H [46-57]
    E("mg1_wave", "MG 1 Wave", ["Triangle", "Saw Down", "Saw Up", "Square", "Pink Noise", "White Noise"], 0, "mod",
      260, 180, fb=46, sw=160, sh=56, rows=2),
    K("mg1_freq", "MG 1 Freq", 0, 10, 4, "mod", 590, 180, fb=47),
    E("mg1_sync", "MG 1 Sync", SYNC, 0, "mod", 820, 180, fb=51, widget="popup", w=220, h=56),
    E("mg_select", "MG Signal", ["S/H", "MG 1"], 1, "mod", 1060, 180, fb=49, sw=110, sh=56),
    K("mg2_freq", "MG 2 Freq", 0, 10, 3, "mod", 120, 450, fb=52),
    E("mg2_sync", "MG 2 Sync", SYNC, 0, "mod", 350, 450, fb=53, widget="popup", w=220, h=56),
    K("sh_clock", "S/H Clock", 0, 10, 5, "mod", 590, 450, fb=54),
    T("sh_sync", "S/H Synchro", 0, "mod", 820, 400, fb=55),
    E("sh_host", "S/H Host Sync", SYNC, 0, "mod", 820, 520, fb=57, widget="popup", w=220, h=56),
    # ---- GENERAL ENVELOPE [58-63], VOLTAGE PROCESSORS [65-70], utilities (CHORG) + MANUAL TRG1
    E("geg_trigger", "GEG Trigger", ["Off", "1", "2", "3", "4", "5"], 1, "geg", 190, 170, fb=58, sw=105, sh=56, rows=2),
    K("geg_delay", "Delay", 0, 10, 0, "geg", 440, 170, fb=59),
    K("geg_attack", "Attack", 0, 10, 2, "geg", 620, 170, fb=60),
    K("geg_release", "Release", 0, 10, 4, "geg", 800, 170, fb=61),
    T("geg_auto", "Auto", 0, "geg", 975, 140, fb=62),
    E("geg_polarity", "Polarity", ["Positive", "Negative"], 0, "geg", 1140, 140, fb=63, sw=110, sh=52),
    K("vp1_a", "VP 1 Limiter A", -5, 5, 5, "geg", 110, 450, fb=65),
    K("vp1_b", "VP 1 Limiter B", -5, 5, -5, "geg", 270, 450, fb=66),
    K("vp2_a", "VP 2 Limiter A", -5, 5, 5, "geg", 430, 450, fb=68),
    K("vp2_b", "VP 2 Limiter B", -5, 5, -5, "geg", 590, 450, fb=69),
    E("vp2_src", "VP 2 Input", ["VP 2 In", "VP 1"], 0, "geg", 590, 580, fb=70, sw=120, sh=48),
    K("xy_x", "X", -5, 5, 0, "geg", 790, 450),
    K("xy_y", "Y", -5, 5, 0, "geg", 950, 450),
    K("add_level", "Add Amp", 0, 10, 10, "geg", 1110, 450),
    B("manual_trg1", "Manual TRG 1", "geg", 975, 260),
    # ---- TEMPERAMENT [72-83] + templates
    *[K("tune_%s" % n.replace("#", "s").lower(), "Tune %s" % n, -50, 50, 0, "tun",
        100 + (i % 6) * 160, 190 if i < 6 else 430, fb=72 + i, unit="ct", intd=True) for i, n in enumerate(NOTE_NAMES)],
    E("temperament", "Temperament", TEMPERAMENTS, 0, "tun", 1125, 190, widget="popup", w=270, h=56),
    K("master_tune", "Master Tune", -50, 50, 0, "tun", 1125, 430, unit="ct", intd=True),
    # ---- SETUP: voices, MIDI, clocks [84-91]
    E("voices", "Voices", ["8", "12", "16", "24", "32", "48"], 2, "setup", 230, 170, sw=110, sh=56, rows=2),
    K("pb_range", "PB Range", 0, 12, 2, "setup", 520, 170, fb=5, unit="st", intd=True),
    E("clk1_rate", "CLK 1 Rate", DIVS, 7, "setup", 760, 150, fb=84, widget="popup", w=220, h=56),
    E("clk2_rate", "CLK 2 Rate", DIVS, 5, "setup", 1020, 150, fb=85, widget="popup", w=220, h=56),
    K("trg1_cc", "TRG 1 CC", 0, 127, 80, "setup", 130, 450, fb=86, intd=True),
    K("trg2_cc", "TRG 2 CC", 0, 127, 81, "setup", 300, 450, fb=87, intd=True),
    K("vc1_cc", "VC 1 CC", 0, 127, 16, "setup", 470, 450, fb=88, intd=True),
    K("vc2_cc", "VC 2 CC", 0, 127, 17, "setup", 640, 450, fb=89, intd=True),
    K("vc3_cc", "VC 3 CC", 0, 127, 18, "setup", 810, 450, fb=90, intd=True),
    K("vc4_cc", "VC 4 CC", 0, 127, 19, "setup", 980, 450, fb=91, intd=True),
]
CTRL = {c["key"]: c for c in CONTROLS}

# ------------------------------------------------------------------------------------------------------ the jacks
# Outputs feed one input each (the PS-3100 way: a cable from one socket to another); the junctions copy a signal to
# two more outputs. An input left unpatched uses its hard-wired default, as on the hardware.
# (key, label, type, info)   type: cv (volts) or trig
OUTS = [
    ("geg", "GEG", "cv", "General envelope, -5..0 or 0..+5 V by polarity"),
    ("gep", "GE+", "cv", "General envelope, always 0..+5 V"),
    ("mg", "MG", "cv", "MG signal (MG 1 or S/H) through the MG VCA, -5..+5 V"),
    ("mg1", "MG 1", "cv", "MG 1, -5..+5 V"),
    ("mg2", "MG 2", "cv", "MG 2, -5..+5 V"),
    ("sh", "S/H", "cv", "Sample & hold, -5..+5 V"),
    ("vp1", "VP 1", "cv", "Voltage processor 1, between its limiters"),
    ("vp2", "VP 2", "cv", "Voltage processor 2, between its limiters"),
    ("key", "KEY", "cv", "Last key played, -5..+5 V over the keyboard"),
    ("pb", "PB", "cv", "Pitch bend, -5..+5 V"),
    ("pbp", "PB+", "cv", "Pitch bend, 0..+5 V"),
    ("mw", "MW", "cv", "Mod wheel, -5..+5 V"),
    ("mwp", "MW+", "cv", "Mod wheel, 0..+5 V"),
    ("vc1", "VC 1", "cv", "MIDI CC (Setup), -5..+5 V"),
    ("vc2", "VC 2", "cv", "MIDI CC (Setup), -5..+5 V"),
    ("vc3", "VC 3", "cv", "MIDI CC (Setup), -5..+5 V"),
    ("vc4", "VC 4", "cv", "MIDI CC (Setup), -5..+5 V"),
    ("rnd", "NOISE", "cv", "White noise, -5..+5 V"),
    ("p5v", "+5 V", "cv", "Constant +5 V"),
    ("m5v", "-5 V", "cv", "Constant -5 V"),
    ("xyx", "X", "cv", "X-Y manipulator X, -5..+5 V"),
    ("xyy", "Y", "cv", "X-Y manipulator Y, -5..+5 V"),
    ("add", "ADD", "cv", "Add amp: inputs 1-4 summed, times its level"),
    ("j1a", "J1 A", "cv", "Junction 1, copy A"),
    ("j1b", "J1 B", "cv", "Junction 1, copy B"),
    ("j2a", "J2 A", "cv", "Junction 2, copy A"),
    ("j2b", "J2 B", "cv", "Junction 2, copy B"),
    ("sng", "SNG", "trig", "Keyboard single trigger (first key)"),
    ("mlt", "MLT", "trig", "Keyboard multiple trigger (every key)"),
    ("mg1c", "MG1 CLK", "trig", "MG 1 clock (each cycle)"),
    ("mg2c", "MG2 CLK", "trig", "MG 2 clock (each cycle)"),
    ("shc", "S/H CLK", "trig", "S/H clock"),
    ("clk1", "CLK 1", "trig", "Tempo clock 1 (Setup rate)"),
    ("clk2", "CLK 2", "trig", "Tempo clock 2 (Setup rate)"),
    ("trg1", "TRG 1", "trig", "MIDI CC trigger 1 and MANUAL TRG 1"),
    ("trg2", "TRG 2", "trig", "MIDI CC trigger 2"),
]
# (key, label, type, default source, info)
INS = [
    ("sg_frq", "SG FRQ", "cv", "geg", "Signal generator pitch mod (GEG / Ext intensity)"),
    ("sg_pwm", "SG PWM", "cv", "mg2", "Pulse width mod (PWM wave)"),
    ("lp_frq", "LP FRQ", "cv", "geg", "Lowpass cutoff mod (GEG / Ext intensity)"),
    ("em_atk", "EM ATK", "cv", None, "Envelope modifier attack time"),
    ("res_frq", "RES FRQ", "cv", None, "Resonator peak frequencies (Ext Mod)"),
    ("vca1", "VCA 1", "cv", "geg", "VCA 1 amplitude (when VCA 1 by GEG is on)"),
    ("vca2", "VCA 2", "cv", "vp1", "VCA 2 amplitude (when VCA 2 by VP 1 is on)"),
    ("mg_amt", "MG AMT", "cv", None, "MG VCA: amount of the MG signal"),
    ("mg1_frq", "MG1 FRQ", "cv", None, "MG 1 frequency"),
    ("sh_in", "S/H IN", "cv", "mg1", "Sample & hold input"),
    ("vp1_in", "VP1 IN", "cv", None, "Voltage processor 1 input"),
    ("vp2_in", "VP2 IN", "cv", None, "Voltage processor 2 input"),
    ("add1", "ADD 1", "cv", None, "Add amp input 1"),
    ("add2", "ADD 2", "cv", None, "Add amp input 2"),
    ("add3", "ADD 3", "cv", None, "Add amp input 3"),
    ("add4", "ADD 4", "cv", None, "Add amp input 4"),
    ("j1_in", "J1 IN", "cv", None, "Junction 1 input"),
    ("j2_in", "J2 IN", "cv", None, "Junction 2 input"),
    ("em_rel", "EM REL", "trig", None, "Envelope modifier: release every voice"),
    ("geg_trg", "GEG TRG", "trig", "kbd", "General envelope trigger (default: the keyboard)"),
]
CV_OUTS = [o for o in OUTS if o[2] == "cv"]
TRIG_OUTS = [o for o in OUTS if o[2] == "trig"]
CV_INS = [i for i in INS if i[2] == "cv"]
TRIG_INS = [i for i in INS if i[2] == "trig"]

# Patch bay page: where each jack sits. Inputs on the top two rows, outputs on the three rows below, grouped as on a
# panel (envelopes and MGs, processors, performance, MIDI CV, constants and utilities, triggers).
JACK_DX = 98
def _row(keys, y, x0=80):
    return {k: (x0 + i * JACK_DX, y) for i, k in enumerate(keys)}
JACKS = {}
JACKS.update(_row([i[0] for i in INS[:10]], 150))
JACKS.update(_row([i[0] for i in INS[10:]], 255))
JACKS.update(_row(["geg", "gep", "mg", "mg1", "mg2", "sh", "vp1", "vp2", "rnd", "key", "pb", "pbp"], 380))
JACKS.update(_row(["mw", "mwp", "vc1", "vc2", "vc3", "vc4", "p5v", "m5v", "xyx", "xyy", "add", "j1a"], 475))
JACKS.update(_row(["j1b", "j2a", "j2b", "sng", "mlt", "mg1c", "mg2c", "shc", "clk1", "clk2", "trg1", "trg2"], 570))
assert set(JACKS) == {o[0] for o in OUTS} | {i[0] for i in INS}, "every jack placed once"
JACK_R = 21                  # socket radius on the patch page
CABLE_TILE = 128            # cable pictures are cut on this grid (post_skin.tile_pieces): memory vs component count
CABLE_COLOURS = [(216, 90, 48), (29, 158, 117), (239, 159, 39), (55, 138, 221), (212, 83, 126), (127, 119, 221),
                 (99, 153, 34), (226, 75, 74)]

# Header on every zoomed page: back to the overview, previous / next section.
NAV = [("nav_zoom", "OVERVIEW", 90, 38), ("nav_prev", "<", 240, 38), ("nav_next", ">", 350, 38)]


# Cable and ring pictures are switched by parameters of at most JACK_GROUP + 1 positions (0.1.4). 0.1.2 and 0.1.3 used
# one 37-position parameter per output; on the Force nothing ever appeared, and nothing above 11 positions (the view) has
# been seen working there. So each output's cable is split over small parameters: inputs of its type in groups of
# JACK_GROUP, one parameter per group ("-" or which input of the group), for the patch page (cp_) and the overview (co_);
# the ring of the output waiting for an input likewise over hd_<g>.
JACK_GROUP = 9


def groups(items):
    return [items[i:i + JACK_GROUP] for i in range(0, len(items), JACK_GROUP)]


def cable_groups(out):
    """[(group index, [inputs])] an output's cable can reach."""
    return list(enumerate(groups([i for i in INS if i[2] == out[2]])))


def cable_param(prefix, out, j):
    """(param key, option index, option count) showing out's cable to input j (prefix cp = patch page, co = overview)."""
    ins = [i for i in INS if i[2] == out[2]]
    t = ins.index(j)
    g = t // JACK_GROUP
    n = len(groups(ins)[g])
    return "%s_%s_%d" % (prefix, out[0], g), 1 + t % JACK_GROUP, n + 1


def held_in_param(j):
    """(key, option, count) of the ring on input j while it waits for an output (input tapped first, 0.1.4)."""
    ii = INS.index(j)
    g = ii // JACK_GROUP
    return "hi_%d" % g, 1 + ii % JACK_GROUP, len(groups(INS)[g]) + 1


def held_param(out):
    oi = OUTS.index(out)
    g = oi // JACK_GROUP
    return "hd_%d" % g, 1 + oi % JACK_GROUP, len(groups(OUTS)[g]) + 1

