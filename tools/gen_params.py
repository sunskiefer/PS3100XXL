#!/usr/bin/env python3
"""Writes everything that follows from tools/spec.py:

    python3 tools/gen_params.py

  params.json        the VST parameter list for mpc-vst-plugins' gen_vst.py (index = order, append-only once shipped)
  src/param_ids.h    P_<KEY> indices, jack tables and temperament tables for the engine
  layout.conf        the skin layout (one tab; every section is a when=view:<x> mode panel)
  docs/INVENTORY.md  the full control and jack list, checked against the build
"""
import json
import re
import math
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec  # noqa: E402

Y0 = 86   # Force Shadow y of the plugin page's top


# ------------------------------------------------------------------------------------------------ temperaments
PC = 1200 * math.log2(3 ** 12 / 2 ** 19)          # Pythagorean comma, 23.46 cents
SC = 1200 * math.log2(81 / 80)                    # syntonic comma, 21.51 cents
FIFTH = 1200 * math.log2(1.5)
CIRCLE = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]   # C G D A E B F# C# G# D# A# F, by semitone


def from_circle(tempers):
    """12 fifth tempers (cents, C-G first, F-C last) -> cents off equal temperament per pitch class (C = 0)."""
    cents = [0.0] * 12
    pos = 0.0
    for i in range(11):
        pos += FIFTH - tempers[i]
        cents[CIRCLE[i + 1]] = (pos % 1200) - CIRCLE[i + 1] * 100
    return [((c + 600) % 1200) - 600 for c in cents]


def chain(temper):
    """A meantone-style chain Eb..G# (every fifth tempered alike, the wolf between G# and Eb)."""
    cents = [0.0] * 12
    for n in range(-3, 9):                        # Eb (-3 fifths) .. G# (+8)
        pc = (7 * n) % 12
        cents[pc] = ((n * (FIFTH - temper)) % 1200) - pc * 100
    return [((c + 600) % 1200) - 600 for c in cents]


def tempers(pairs):
    t = [0.0] * 12
    for idx, amt in pairs:
        t[idx] = amt
    return t


JUST = [1, 16 / 15, 9 / 8, 6 / 5, 5 / 4, 4 / 3, 45 / 32, 3 / 2, 8 / 5, 5 / 3, 9 / 5, 15 / 8]
TEMPER_CENTS = {
    "Equal": [0.0] * 12,
    "Pythagorean": chain(0.0),
    "Just": [1200 * math.log2(r) - 100 * i for i, r in enumerate(JUST)],
    "Meantone 1/3": chain(SC / 3),
    "Meantone 2/7": chain(SC * 2 / 7),
    "Meantone 1/4": chain(SC / 4),
    "Meantone 1/5": chain(SC / 5),
    "Meantone 1/6": chain(SC / 6),
    # circle positions: 0 C-G, 1 G-D, 2 D-A, 3 A-E, 4 E-B, 5 B-F#, 6 F#-C#, ..., 11 F-C
    "Werckmeister III": from_circle(tempers([(0, PC / 4), (1, PC / 4), (2, PC / 4), (5, PC / 4)])),
    "Kirnberger II": from_circle(tempers([(2, SC / 2), (3, SC / 2), (6, PC - SC)])),
    "Kirnberger III": from_circle(tempers([(0, SC / 4), (1, SC / 4), (2, SC / 4), (3, SC / 4), (6, PC - SC)])),
    "Vallotti": from_circle(tempers([(11, PC / 6), (0, PC / 6), (1, PC / 6), (2, PC / 6), (3, PC / 6), (4, PC / 6)])),
    "Young II": from_circle(tempers([(i, PC / 6) for i in range(6)])),
    "Kellner": from_circle(tempers([(0, PC / 5), (1, PC / 5), (2, PC / 5), (3, PC / 5), (5, PC / 5)])),
}
assert list(TEMPER_CENTS) == spec.TEMPERAMENTS
for name, c in TEMPER_CENTS.items():
    assert all(abs(x) <= 50 for x in c), (name, c)


# ------------------------------------------------------------------------------------------------ parameters
def param_of(c):
    if c["kind"] == "knob":
        p = {"key": c["key"], "name": c["name"], "min": float(c["min"]), "max": float(c["max"]),
             "default": float(c["default"]), "dynamic_display": True}
        if c.get("int"):
            p["display"] = "int"
        if c.get("unit"):
            p["unit"] = c["unit"]
        return p
    if c["kind"] in ("toggle", "enum"):
        return {"key": c["key"], "name": c["name"], "options": c["options"], "default": c["default"]}
    if c["kind"] == "button":
        return {"key": c["key"], "name": c["name"], "min": 0.0, "max": 1.0, "default": 0.0, "momentary": True,
                "type": "trigger"}
    raise ValueError(c)


def trigger(key, name):
    return {"key": key, "name": name, "min": 0.0, "max": 1.0, "default": 0.0, "momentary": True, "type": "trigger"}


def cable_opts(out_type):
    ins = [i for i in spec.INS if i[2] == out_type]
    return ["-"] + ["P " + i[1] for i in ins] + ["O " + i[1] for i in ins]


def build_params():
    P = [param_of(c) for c in spec.CONTROLS]
    P.append({"key": "view", "name": "View", "options": ["Overview"] + [v[2].title() for v in spec.VIEWS[1:]], "default": 0})
    # the section switches: the 16 Q-Links' names follow the section, so these ask MPC to redraw (mpc-vst-plugins #486)
    P += [dict(trigger(k, lbl), refresh_display=True) for k, lbl, _, _ in spec.NAV]
    P += [dict(trigger("go_" + v[0], "Go " + v[2].title()), refresh_display=True) for v in spec.VIEWS[1:]]
    P += [trigger("tap_" + j[0], "Jack " + j[1]) for j in spec.OUTS + spec.INS]
    P += [{"key": "cab_" + o[0], "name": "Cable " + o[1], "options": cable_opts(o[2]), "default": 0, "poll": False}
          for o in spec.OUTS]
    P.append({"key": "held", "name": "Held Output", "options": ["-"] + [o[1] for o in spec.OUTS], "default": 0})
    P.append({"key": "geg_led", "name": "GEG LED", "options": spec.OFF_ON, "default": 0})
    P.append({"key": "patch_info", "name": "Patch Info", "min": 0.0, "max": 0.0, "default": 0.0, "display": "string"})
    P += [{"key": "ql%d" % (i + 1), "name": "Q-Link %d" % (i + 1), "min": 0.0, "max": 1.0, "default": 0.0,
           "dynamic_name": True, "dynamic_display": True} for i in range(16)]
    # 0.1.3, appended so every shipped index stays put (params.lock):
    # in_sec: 1 on any section page, 0 on the overview -- the header buttons show on it, one instance each, so a press
    # never swaps the button under the finger for another page's copy (the page-arrow glitch of 0.1.2);
    # pop_<key>: a pop-up list's open flag, owned by the engine (the framework's own "<key>__open" is wrapper-only and
    # stays open across a page change, invisibly covering the next page and taking its touches). The engine closes it on
    # a pick and on every page change.
    P.append({"key": "in_sec", "name": "In Section", "options": ["Overview", "Section"], "default": 0})
    P += [{"key": "pop_" + c["key"], "name": c["name"] + " List", "options": ["Closed", "Open"], "default": 0}
          for c in spec.CONTROLS if c["kind"] == "enum" and c["widget"] == "popup"]
    # 0.1.4, appended: the cable and ring pictures' switches, at most JACK_GROUP + 1 positions each (spec.py)
    for prefix, where in (("cp", "Patch"), ("co", "Overview")):
        for o in spec.OUTS:
            for g, ins in spec.cable_groups(o):
                P.append({"key": "%s_%s_%d" % (prefix, o[0], g), "name": "%s %s %s %d" % ("Cable", where[:3], o[1], g + 1),
                          "options": ["-"] + [i[1] for i in ins], "default": 0, "poll": False})
    for g, outs in enumerate(spec.groups(spec.OUTS)):
        P.append({"key": "hd_%d" % g, "name": "Held %d" % (g + 1), "options": ["-"] + [o[1] for o in outs], "default": 0})
    for g, ins in enumerate(spec.groups(spec.INS)):   # an input tapped first waits for its output (either order)
        P.append({"key": "hi_%d" % g, "name": "Held In %d" % (g + 1), "options": ["-"] + [i[1] for i in ins], "default": 0})
    keys = [p["key"] for p in P]
    assert len(keys) == len(set(keys)), "duplicate keys"
    return P


def write_params(P):
    secs = []
    for v in spec.VIEWS[1:]:
        secs.append({"label": v[2], "keys": [c["key"] for c in spec.CONTROLS if c["view"] == v[0]]})
    with open(os.path.join(ROOT, "params.json"), "w") as f:
        json.dump({"name": "PS3100XXL", "params": P, "sections": secs}, f, indent=1)
        f.write("\n")


def cid(k):
    return "P_" + k.upper()


def write_header(P):
    L = ["// Generated by tools/gen_params.py from tools/spec.py -- do not edit.", "#pragma once", ""]
    for i, p in enumerate(P):
        L.append("#define %s %d" % (cid(p["key"]), i))
    L.append("#define P_COUNT %d" % len(P))
    def num(p, k, d):
        t = "%.6g" % float(p.get(k, d))
        return t + (".0f" if "." not in t and "e" not in t else "f")
    L.append("static const char *const P_KEY[P_COUNT] = {%s};" % ", ".join('"%s"' % p["key"] for p in P))
    L.append("static const char *const P_NAME[P_COUNT] = {%s};" % ", ".join('"%s"' % p["name"] for p in P))
    L.append("static const char *const P_UNIT[P_COUNT] = {%s};" % ", ".join('"%s"' % p.get("unit", "") for p in P))
    L.append("static const float P_MIN[P_COUNT] = {%s};" % ", ".join(num(p, "min", 0) for p in P))
    L.append("static const float P_MAX[P_COUNT] = {%s};" % ", ".join(
        ("%d.0f" % (len(p["options"]) - 1)) if "options" in p else num(p, "max", 1) for p in P))
    L.append("static const float P_DEF[P_COUNT] = {%s};" % ", ".join(num(p, "default", 0) for p in P))
    L.append("static const unsigned char P_NOPTS[P_COUNT] = {%s};" % ", ".join(str(len(p.get("options", []))) for p in P))
    for i, p in enumerate(P):
        if "options" in p:
            L.append("static const char *const OPTS_%d[] = {%s};" % (i, ", ".join('"%s"' % o for o in p["options"])))
    L.append("static const char *const *const P_OPT[P_COUNT] = {%s};" % ", ".join(
        ("OPTS_%d" % i) if "options" in p else "0" for i, p in enumerate(P)))
    L.append("static const unsigned char P_INT[P_COUNT] = {%s};" % ", ".join(
        "1" if p.get("display") == "int" else "0" for p in P))
    L.append("#define N_CONTROLS %d   // the sound parameters come first: indices 0..N_CONTROLS-1" % len(spec.CONTROLS))
    L.append("")
    L.append("// views (the 'view' parameter's options)")
    for i, v in enumerate(spec.VIEWS):
        L.append("#define V_%s %d" % (v[0].upper(), i))
    L.append("#define N_VIEWS %d" % len(spec.VIEWS))
    L.append("")
    L.append("// jacks: outputs O_*, inputs I_*")
    for i, o in enumerate(spec.OUTS):
        L.append("#define O_%s %d" % (o[0].upper(), i))
    L.append("#define N_OUTS %d" % len(spec.OUTS))
    for i, j in enumerate(spec.INS):
        L.append("#define I_%s %d" % (j[0].upper(), i))
    L.append("#define N_INS %d" % len(spec.INS))
    L.append("static const char *const OUT_KEY[N_OUTS] = {%s};" % ", ".join('"%s"' % o[0] for o in spec.OUTS))
    L.append("static const char *const OUT_LABEL[N_OUTS] = {%s};" % ", ".join('"%s"' % o[1] for o in spec.OUTS))
    L.append("static const char *const OUT_INFO[N_OUTS] = {%s};" % ", ".join('"%s"' % o[3] for o in spec.OUTS))
    L.append("static const unsigned char OUT_TRIG[N_OUTS] = {%s};" % ", ".join(
        "1" if o[2] == "trig" else "0" for o in spec.OUTS))
    L.append("static const char *const IN_KEY[N_INS] = {%s};" % ", ".join('"%s"' % j[0] for j in spec.INS))
    L.append("static const char *const IN_LABEL[N_INS] = {%s};" % ", ".join('"%s"' % j[1] for j in spec.INS))
    L.append("static const char *const IN_INFO[N_INS] = {%s};" % ", ".join('"%s"' % j[4] for j in spec.INS))
    L.append("static const unsigned char IN_TRIG[N_INS] = {%s};" % ", ".join(
        "1" if j[2] == "trig" else "0" for j in spec.INS))
    # an input's index among the inputs of its own type (the cable parameter's option = 1 + that, or + count for the
    # overview's small copy)
    L.append("static const unsigned char IN_TYPED[N_INS] = {%s};" % ", ".join(
        str([x for x in spec.INS if x[2] == j[2]].index(j)) for j in spec.INS))
    # the cable / ring picture switches (0.1.4): for each, which kind (0 patch cable, 1 overview cable, 2 ring),
    # which output (or group of outputs for a ring) and which group of inputs
    vis = [p for p in P if re.match(r"(cp|co)_.*_\d+$|hd_\d+$|hi_\d+$", p["key"])]
    first = P.index(vis[0])
    assert [p["key"] for p in P[first:first + len(vis)]] == [p["key"] for p in vis], "picture switches contiguous"
    okeys = [o[0] for o in spec.OUTS]
    kinds, outs, grps = [], [], []
    for p in vis:
        k = p["key"]
        if k.startswith("hd_"):
            kinds.append(2); outs.append(-1); grps.append(int(k[3:]))
        elif k.startswith("hi_"):
            kinds.append(3); outs.append(-1); grps.append(int(k[3:]))
        else:
            m = re.match(r"(cp|co)_(.+)_(\d+)$", k)
            kinds.append(0 if m.group(1) == "cp" else 1); outs.append(okeys.index(m.group(2))); grps.append(int(m.group(3)))
    L.append("// cable / ring picture switches")
    L.append("#define JACK_GROUP %d" % spec.JACK_GROUP)
    L.append("#define P_VIS_FIRST %d" % first)
    L.append("#define N_VIS %d" % len(vis))
    L.append("static const unsigned char VIS_KIND[N_VIS] = {%s};" % ", ".join(map(str, kinds)))
    L.append("static const signed char VIS_OUT[N_VIS] = {%s};" % ", ".join(map(str, outs)))
    L.append("static const unsigned char VIS_GROUP[N_VIS] = {%s};" % ", ".join(map(str, grps)))
    pops = [c["key"] for c in spec.CONTROLS if c["kind"] == "enum" and c["widget"] == "popup"]
    L.append("// pop-up lists: the enum each pop_<key> opens")
    L.append("#define N_POPS %d" % len(pops))
    L.append("static const short POP_ENUM[N_POPS] = {%s};" % ", ".join(cid(k) for k in pops))
    L.append("#define N_CV_INS %d" % len(spec.CV_INS))
    L.append("#define N_TRIG_INS %d" % len(spec.TRIG_INS))
    L.append("")
    L.append("// the views' controls in Q-Link order (top row left to right, then the next): up to 16 per view, -1 = none")
    rows = []
    for v in spec.VIEWS:
        if v[0] == "overview":
            keys = ["lp_cutoff", "lp_peak", "lp_expand", "em_attack", "em_decay", "em_sustain", "res_int", "final_vol",
                    "sg_fm_mg1", "lp_fm_mg1", "mg1_freq", "sg_pwm_int", "geg_attack", "geg_release", "amp_mod", "direct_vol"]
        else:
            cs = [c for c in spec.CONTROLS if c["view"] == v[0]]
            cs.sort(key=lambda c: (round(c["cy"] / 60), c["cx"]))
            keys = [c["key"] for c in cs][:16]
        ids = [cid(k) for k in keys] + ["-1"] * (16 - len(keys))
        rows.append("    {%s}," % ", ".join(ids))
    L.append("static const short VIEW_QLINKS[N_VIEWS][16] = {")
    L += rows
    L.append("};")
    L.append("")
    L.append("// temperament templates: cents off equal temperament, C..B")
    L.append("static const float TEMPERAMENT_CENTS[%d][12] = {" % len(spec.TEMPERAMENTS))
    for name in spec.TEMPERAMENTS:
        L.append("    {%s},  // %s" % (", ".join("%.3ff" % c for c in TEMPER_CENTS[name]), name))
    L.append("};")
    L.append("static const float DIV_BEATS[%d] = {%s};" % (len(spec.DIV_BEATS), ", ".join(
        "%.6ff" % b for b in spec.DIV_BEATS)))
    L.append("")
    with open(os.path.join(ROOT, "src", "param_ids.h"), "w") as f:
        f.write("\n".join(L))


# ------------------------------------------------------------------------------------------------ layout.conf
THEME = """scale_names=1
label_scale=1.25
theme_bg=242424
theme_panel=242424
theme_line=bfbfbf
theme_ink=f2f2f2
theme_ink_dim=c8c8c8
theme_ink_faint=7a7a7a
theme_accent=f07a1e
theme_accent_hi=ffffff
theme_knob_face=151515
theme_knob_ring=3c3c3c
theme_knob_dot=f2f2f2
theme_bar=1a1a1a
theme_seg_active=f07a1e
theme_seg_inactive=151515
theme_seg_active_tx=111111
theme_btn_text=f2f2f2
theme_tab_on=f07a1e
theme_tab_on_tx=111111
theme_lcd=101010
theme_box=151515"""


def layout_line(c):
    v = "when=view:%d" % spec.VIEW_KEYS.index(c["view"])
    x, y = c["cx"], c["cy"] + Y0
    if c["kind"] == "knob":
        return 'knob cx=%d cy=%d r=%d label="%s" key=%s ns=0 vs=24 bw=150 %s' % (
            x, y, c["r"], c["name"].upper(), c["key"], v)
    if c["kind"] == "toggle":
        return 'toggle cx=%d cy=%d label="%s" key=%s bw=130 ns=0 %s' % (x, y, c["name"].upper(), c["key"], v)
    if c["kind"] == "button":
        return 'button cx=%d cy=%d label="%s" key=%s %s' % (x, y, c["name"].upper(), c["key"], v)
    if c["widget"] == "popup":
        return 'popup cx=%d cy=%d w=%d h=%d label="%s" key=%s %s' % (x, y, c["w"], c["h"], c["name"].upper(), c["key"], v)
    return 'enum_h cx=%d cy=%d sw=%d sh=%d rows=%d label="%s" key=%s %s' % (
        x, y, c["sw"], c["sh"], c["rows"], c["name"].upper(), c["key"], v)


def write_layout():
    L = ["# PS3100XXL page layout. GENERATED by tools/gen_params.py from tools/spec.py -- edit spec.py, not this.",
         "# One tab; each section of the panel is a mode panel shown while 'view' is at it (the zoom). The overview",
         "# tiles, the jacks and the cables are placed and drawn by tools/post_skin.py.",
         THEME,
         "qlinks_track = " + ",".join("ql%d" % (i + 1) for i in range(16)),
         "", "[tab PS3100XXL]"]
    for k, lbl, x, y in spec.NAV:   # one instance each, shown on every section page (in_sec), never swapped mid-press
        L.append('button cx=%d cy=%d label="%s" key=%s when=in_sec:1' % (x, y + Y0, lbl, k))
    for v in spec.VIEWS[1:]:
        x, y, w, h = spec.TILES[v[0]]
        L.append('button cx=%d cy=%d label="" key=go_%s when=view:0' % (x + w // 2, y + h // 2 + Y0, v[0]))
    for j in spec.OUTS + spec.INS:
        x, y = spec.JACKS[j[0]]
        L.append('button cx=%d cy=%d label="" key=tap_%s when=view:%d' % (x, y + Y0, j[0], spec.VIEW_KEYS.index('patch')))
    L.append('readout cx=930 cy=%d w=640 h=50 label="" key=patch_info when=view:%d' % (38 + Y0, spec.VIEW_KEYS.index('patch')))
    L.append('readout cx=930 cy=%d w=640 h=50 label="" key=patch_info when=view:0' % (38 + Y0))   # diagnostics line on the overview too
    for c in spec.CONTROLS:
        L.append(layout_line(c))
    L.append('qlinks "PS3100XXL" = ' + ",".join("ql%d" % (i + 1) for i in range(16)))
    with open(os.path.join(ROOT, "layout.conf"), "w") as f:
        f.write("\n".join(L) + "\n")


# ------------------------------------------------------------------------------------------------ inventory
def write_inventory():
    L = ["# PS3100XXL inventory", "",
         "Every control and jack of the instrument, generated from `tools/spec.py` (the build checks the skin "
         "against the same list). FB-3100 IDs are the parameter numbers in the Full Bucket FB-3100 1.2 manual.", "",
         "Left out, and why: the external audio input (an MPC instrument plugin receives no audio), Scala `.scl` "
         "import (no file picker on MPC) and FB-3100's program/bank file menu (MPC's PRESET menu and project save "
         "cover it).", ""]
    for v in spec.VIEWS[1:]:
        cs = [c for c in spec.CONTROLS if c["view"] == v[0]]
        if v[0] == "patch":
            continue
        L += ["## " + v[1].title(), "", "| Control | Key | Range | FB-3100 |", "|---|---|---|---|"]
        for c in cs:
            if c["kind"] == "knob":
                rng = "%g .. %g %s" % (c["min"], c["max"], c.get("unit", ""))
            elif c["kind"] == "button":
                rng = "push"
            else:
                rng = " / ".join(c["options"]) if len(c["options"]) <= 6 else "%d options" % len(c["options"])
            L.append("| %s | `%s` | %s | %s |" % (c["name"], c["key"], rng.strip(), c["fb"] if c["fb"] is not None else "-"))
        L.append("")
    L += ["## Patch bay", "", "Each output feeds one input (a junction gives two more copies). An input with no "
          "cable uses its default, as on the PS-3100.", "", "### Outputs", "", "| Jack | Type | Signal |", "|---|---|---|"]
    for o in spec.OUTS:
        L.append("| %s | %s | %s |" % (o[1], o[2], o[3]))
    L += ["", "### Inputs", "", "| Jack | Type | Default when unpatched | Destination |", "|---|---|---|---|"]
    for j in spec.INS:
        d = {None: "-", "kbd": "keyboard"}.get(j[3], dict((o[0], o[1]) for o in spec.OUTS).get(j[3], j[3]))
        L.append("| %s | %s | %s | %s |" % (j[1], j[2], d, j[4]))
    L += ["", "%d controls, %d outputs, %d inputs." % (len(spec.CONTROLS), len(spec.OUTS), len(spec.INS)), ""]
    with open(os.path.join(ROOT, "docs", "INVENTORY.md"), "w") as f:
        f.write("\n".join(L))


# ------------------------------------------------------------------------------------------------ factory presets
# Every preset sets every sound parameter (defaults below the overrides), so a preset always sounds the same whatever
# was loaded before. Cables are not parameters: a preset keeps the patch on the patch page.
PRESETS = [
    ("Init", dict()),
    ("PS Strings", dict(sg_wave=1, lp_cutoff=6.4, lp_peak=1.5, lp_expand=3, em_attack=3.2, em_decay=5.5, em_sustain=8,
                        em_release=2, res_int=3, res_f1=3.4, res_f2=5.2, res_f3=7.4, ensemble=1, final_vol=7)),
    ("Brass Section", dict(sg_wave=1, lp_cutoff=3.2, lp_peak=3, lp_expand=6.5, em_attack=2.2, em_decay=4.2,
                           em_sustain=7, em_release=1, velocity=4, ensemble=0, final_vol=7)),
    ("Divide-Down Organ", dict(sg_wave=2, lp_cutoff=8.5, lp_peak=0, lp_expand=0, em_attack=0.1, em_decay=5,
                               em_sustain=10, em_release=1, ensemble=1, final_vol=6.5)),
    ("Resonator Choir", dict(sg_wave=5, sg_pwm_int=5, lp_cutoff=5.6, lp_expand=2, em_attack=3.8, em_decay=6,
                             em_sustain=8, res_int=8.5, res_f1=4.0, res_f2=5.6, res_f3=7.1, res_mg2=1, mg2_freq=2.2,
                             ensemble=1, final_vol=7.5)),
    ("PWM Pad", dict(sg_wave=5, sg_pwm_int=7.5, mg2_freq=3, lp_cutoff=5.5, lp_peak=2, lp_expand=3, em_attack=4.5,
                     em_decay=6, em_sustain=8, ensemble=1, final_vol=7)),
    ("Pluck", dict(sg_wave=4, lp_cutoff=2.8, lp_peak=5, lp_expand=8, em_attack=0, em_decay=3.6, em_sustain=0,
                   em_release=1, velocity=5, ensemble=0, final_vol=7.5)),
    ("Clavi", dict(sg_wave=3, lp_cutoff=4.8, lp_peak=4, lp_expand=6, lp_balance=2, em_attack=0, em_decay=3.2,
                   em_sustain=0, em_release=0, velocity=6, ensemble=0, final_vol=7.5)),
    ("Vibrato Lead", dict(sg_wave=1, sg_octave=2, sg_fm_on=1, sg_fm_mg1=1.2, mg1_freq=4.5, mg_select=1, lp_cutoff=5,
                          lp_peak=4, lp_expand=4, em_attack=0.6, em_decay=5, em_sustain=8, ensemble=0, final_vol=7)),
    ("Ring Bells", dict(sg_wave=0, sg_octave=2, am_mg1=1, amp_mod=8.5, mg1_freq=7.6, lp_cutoff=9, em_attack=0,
                        em_decay=6.5, em_sustain=0, em_release=2, res_int=2, ensemble=1, final_vol=7)),
    ("S/H Bubbles", dict(sg_wave=1, mg_select=0, sh_clock=5, lp_fm_on=1, lp_fm_mg1=6.5, lp_cutoff=4, lp_peak=7,
                         em_attack=0.3, em_decay=5, em_sustain=7, ensemble=1, final_vol=7)),
    ("GEG Sweep", dict(sg_wave=1, geg_trigger=1, geg_attack=6.5, geg_release=6.5, geg_delay=2, lp_fm_on=1,
                       lp_fm_geg=7, lp_cutoff=2, lp_peak=6, em_attack=1, em_sustain=9, ensemble=1, final_vol=7)),
    ("Tremolo Piano", dict(sg_wave=0, am_mg1=1, amp_mod=3, mg1_freq=4.4, lp_cutoff=6, lp_expand=4, em_attack=0,
                           em_decay=6.5, em_sustain=2.5, em_release=2, velocity=5, ensemble=0, final_vol=7.5)),
    ("Werckmeister Harpsichord", dict(sg_wave=3, sg_octave=2, lp_cutoff=7, lp_expand=3, em_attack=0, em_decay=4.2,
                                      em_sustain=0, em_release=0, temperament=8, ensemble=0, final_vol=7)),
    ("Direct + Resonators", dict(sg_wave=5, sg_pwm_int=4, lp_cutoff=6, em_attack=2, em_sustain=8, res_int=10,
                                 res_f1=2.5, res_f2=4.8, res_f3=8, direct_vol=5, direct_pan=-3, final_pan=3,
                                 ensemble=1, final_vol=6)),
    ("Hold Drone", dict(sg_wave=1, sg_octave=0, em_hold=1, em_attack=1.5, em_sustain=9, lp_cutoff=4.5, lp_peak=5,
                        lp_fm_on=1, lp_fm_mg1=2, mg1_freq=2, res_int=5, ensemble=1, final_vol=6.5)),
]


def write_presets():
    out = []
    for name, over in PRESETS:
        vals = {}
        for c in spec.CONTROLS:
            if c["kind"] == "button":
                continue
            v = over.get(c["key"], c["default"])
            if c["kind"] in ("toggle", "enum"):
                v = c["options"][int(v)]
            vals[c["key"]] = v
        if over.get("temperament"):
            cents = TEMPER_CENTS[spec.TEMPERAMENTS[over["temperament"]]]
            for i, n in enumerate(spec.NOTE_NAMES):
                vals["tune_%s" % n.replace("#", "s").lower()] = int(round(cents[i]))
        out.append({"name": name, "values": vals})
    with open(os.path.join(ROOT, "presets.json"), "w") as f:
        json.dump({"presets": out}, f, indent=1)
        f.write("\n")


def main():
    P = build_params()
    write_params(P)
    write_header(P)
    write_layout()
    write_inventory()
    write_presets()
    print("gen_params: %d parameters (%d controls), %d jacks" % (len(P), len(spec.CONTROLS), len(spec.JACKS)))


if __name__ == "__main__":
    main()
