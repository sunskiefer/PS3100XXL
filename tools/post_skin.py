#!/usr/bin/env python3
"""Turn the generated skin into the PS3100XXL panel.

    python3 tools/post_skin.py "<skin dir>/Plugin Skins" [--preview build/preview]

mpc-vst-plugins' gen_vst.py builds a working skin from layout.conf: one tab whose sections are mode panels shown while
the 'view' parameter is at them. This script then, in the built skin:
  - paints a full panel image per view (labels, knob scales, frames, the patch bay's sockets) and the overview, whose
    tiles are each section's page in miniature, composed from the skin itself at the default settings;
  - redraws the knob filmstrips as the PS-3100's black skirted knobs, the toggles as its orange slide switches, the
    navigation buttons, and makes the jack and overview-tile buttons transparent touch areas;
  - adds the cables: for every output and every input it can reach, one picture of that cable on the patch page and
    a small one on the overview tile, each shown only while its switch parameter says so (IndexedEnabling, the same
    mechanism as the framework's popups and mode panels): cp_/co_<out>_<group>, at most 10 positions each (spec.py).
    The engine sets them from the patch and the view. A ring for the output waiting for its input (hd_<group>) and the
    GEG LED work the same way.
Everything injected goes right after the background, so every control stays on top and keeps its touches.
"""
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec  # noqa: E402

W, H = 1280, 628
FONT = os.path.join(ROOT, "art", "fonts", "TitilliumWeb-SemiBold.ttf")
PANEL = (36, 36, 36)
HEADER = (24, 24, 24)
LINE = (191, 191, 191)
INK = (242, 242, 242)
DIM = (170, 170, 170)
ORANGE = (240, 122, 30)
SS = 2   # supersampling for drawn art
TAB = "PS3100XXL|PS3100XXL"


def font(size):
    return ImageFont.truetype(FONT, int(size))


# ------------------------------------------------------------------------------------------------ the skin's data
def load_param_keys():
    keys = []
    for line in open(os.path.join(ROOT, "build", "params.h")):
        m = re.match(r'\s*\{"([^"]+)",', line)
        if m:
            keys.append(m.group(1))
    return keys


class Skin:
    def __init__(self, folder):
        self.dir = folder
        self.path = os.path.join(folder, "TUI.json")
        self.tui = json.load(open(self.path))
        self.defs_list = self.tui["pageData"]["componentDefinitions"]["localComponentDefinitions"]
        self.defs = {d["key"]: d["value"] for d in self.defs_list}
        self.page = self.defs[TAB]
        self.keys = load_param_keys()
        self.index = {k: i for i, k in enumerate(self.keys)}
        self.params = {p["key"]: p for p in json.load(open(os.path.join(ROOT, "params.json")))["params"]}

    def param_of(self, inst):
        for m in inst["handle remapping"]["map"]:
            if m["key"] == "Data" and m["value"].startswith("Parameter "):
                return self.keys[int(m["value"].split()[1])]
        return None

    def instances(self, key):
        return [c for c in self.page["componentsData"] if self.param_of(c) == key]

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.tui, f, separators=(",", ":"))


def bounds(b):
    return [int(round(float(x))) for x in b.split()]


def bstr(x, y, w, h):
    return "%d %d %d %d" % (x, y, w, h)


def image_instance(name, img, x, y, w, h, handles):
    return {"version": 2,
            "componentData": {"version": 1, "name": name, "type": "Image",
                              "data": {"version": 2, "imageType": "Regular", "colour": "0", "image": img}},
            "handle remapping": {"version": 1, "map": []},
            "bounds": {"version": 2, "acceptsHWFocus": "No", "showWhenDataModelInvalid": "Show", "whenVisible": "Always",
                       "boundsType": "Absolute", "bounds": bstr(x, y, w, h),
                       "additionalInvalidatingHandles": handles}}


# ------------------------------------------------------------------------------------------------ art primitives
def knob_frame(R, angle):
    """One frame of the PS-3100 knob (top view): black skirt, darker cap, white line pointer. RGBA, 2R+10 square."""
    F = 2 * R + 10
    S = 4
    im = Image.new("RGBA", (F * S, F * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = F * S / 2.0
    r = R * S
    # shadow
    d.ellipse([c - r + 2 * S, c - r + 4 * S, c + r + 2 * S, c + r + 4 * S], fill=(0, 0, 0, 110))
    # skirt with a soft rim light at the top-left
    d.ellipse([c - r, c - r, c + r, c + r], fill=(14, 14, 14, 255))
    d.arc([c - r + S, c - r + S, c + r - S, c + r - S], 190, 290, fill=(78, 78, 78, 255), width=int(1.6 * S))
    # cap
    cr = r * 0.74
    for i in range(10):
        k = i / 10.0
        g = int(20 + 14 * (1 - k))
        rr = cr * (1 - k * 0.12)
        d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=(g, g, g, 255))
    d.ellipse([c - cr, c - cr, c + cr, c + cr], outline=(46, 46, 46, 255), width=int(1.2 * S))
    # pointer: a white line on the cap, and a short tick on the skirt
    a = math.radians(angle - 90)
    ca, sa = math.cos(a), math.sin(a)
    d.line([c + ca * cr * 0.18, c + sa * cr * 0.18, c + ca * cr * 0.93, c + sa * cr * 0.93], fill=(245, 245, 245, 255),
           width=max(S * 2, int(r * 0.09)))
    d.line([c + ca * r * 0.80, c + sa * r * 0.80, c + ca * r * 0.97, c + sa * r * 0.97], fill=(230, 230, 230, 255),
           width=max(S * 2, int(r * 0.06)))
    return im.resize((F, F), Image.LANCZOS)


SWEEP = 150.0   # degrees each side of the top, as the PS-3100's printed scales


def write_knob_strips(skin):
    done = []
    for name in sorted(os.listdir(skin.dir)):
        m = re.match(r"sh_knob_r(\d+)\.png$", name)
        if not m:
            continue
        R = int(m.group(1))
        F = 2 * R + 10
        strip = Image.new("RGBA", (F, F * 128), (0, 0, 0, 0))
        for i in range(128):
            strip.paste(knob_frame(R, -SWEEP + 2 * SWEEP * i / 127.0), (0, i * F))
        strip.save(os.path.join(skin.dir, name), optimize=True)
        done.append(R)
    return done


def switch_image(on, w=84, h=40):
    S = 4
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=6 * S, fill=(10, 10, 10, 255), outline=(70, 70, 70, 255),
                        width=S)
    kw = int(w * S * 0.48)
    x0 = w * S - kw - 3 * S if on else 3 * S
    col = ORANGE if on else (150, 72, 18)
    d.rounded_rectangle([x0, 3 * S, x0 + kw, h * S - 3 * S], radius=4 * S, fill=col + (255,))
    for i in range(1, 6):   # ridges, as on the PS-3100's switch caps
        xx = x0 + kw * i / 6.0
        d.line([xx, 7 * S, xx, h * S - 7 * S], fill=(0, 0, 0, 140), width=S)
    return im.resize((w, h), Image.LANCZOS)


def nav_image(label, on, w, h):
    S = 4
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=8 * S, fill=(ORANGE if on else (21, 21, 21)) + (255,),
                        outline=(120, 120, 120, 255), width=2 * S)
    ink = (17, 17, 17, 255) if on else INK + (255,)
    if label in ("<", ">"):
        cx, cy, s = w * S / 2, h * S / 2, h * S * 0.26
        pts = [(cx - s * 0.6, cy - s), (cx - s * 0.6, cy + s), (cx + s * 0.8, cy)] if label == ">" else \
              [(cx + s * 0.6, cy - s), (cx + s * 0.6, cy + s), (cx - s * 0.8, cy)]
        d.polygon(pts, fill=ink)
    else:
        f = font(22 * S)
        d.text((w * S / 2, h * S / 2), label, font=f, fill=ink, anchor="mm")
    return im.resize((w, h), Image.LANCZOS)


def blank(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def tile_highlight(w, h):
    im = Image.new("RGBA", (w, h), (240, 122, 30, 60))
    ImageDraw.Draw(im).rectangle([0, 0, w - 1, h - 1], outline=ORANGE + (255,), width=4)
    return im


def jack_press(r=34):
    im = Image.new("RGBA", (2 * r, 2 * r), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([2, 2, 2 * r - 3, 2 * r - 3], outline=ORANGE + (255,), width=4)
    return im


def ring_image(r=33, w=5):
    S = 4
    im = Image.new("RGBA", (2 * r * S, 2 * r * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([S, S, 2 * r * S - S, 2 * r * S - S], outline=ORANGE + (255,), width=w * S)
    return im.resize((2 * r, 2 * r), Image.LANCZOS)


def led_image(on, r=11):
    S = 4
    im = Image.new("RGBA", (2 * r * S, 2 * r * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, 2 * r * S - 1, 2 * r * S - 1], fill=(20, 20, 20, 255))
    col = (255, 60, 50, 255) if on else (80, 22, 20, 255)
    d.ellipse([3 * S, 3 * S, 2 * r * S - 3 * S, 2 * r * S - 3 * S], fill=col)
    if on:
        d.ellipse([6 * S, 6 * S, 11 * S, 11 * S], fill=(255, 200, 190, 255))
    return im.resize((2 * r, 2 * r), Image.LANCZOS)


# ------------------------------------------------------------------------------------------------ pop-up lists
POP_ARROW_W = 70     # the arrow box on a pop-up field's right end: tap it to open / close the list
POP_TEXT = 24        # option text in an open list (the framework bakes it in its small pixel font)


def pop_arrow_image(open_, w, h):
    S = 4
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=6 * S, fill=ORANGE + (255,) if open_ else (18, 18, 18, 255),
                        outline=(110, 110, 110, 255), width=2 * S)
    d.rectangle([0, 2 * S, 6 * S, h * S - 2 * S], fill=ORANGE + (255,) if open_ else (18, 18, 18, 255))
    d.line([0, 4 * S, 0, h * S - 4 * S], fill=(110, 110, 110, 255), width=2 * S)
    cx, cy, a = w * S / 2.0, h * S / 2.0, 11 * S
    ink = (17, 17, 17, 255) if open_ else ORANGE + (255,)
    if open_:   # pointing up: tap again to close
        d.polygon([(cx - a, cy + a * 0.55), (cx + a, cy + a * 0.55), (cx, cy - a * 0.65)], fill=ink)
    else:
        d.polygon([(cx - a, cy - a * 0.55), (cx + a, cy - a * 0.55), (cx, cy + a * 0.65)], fill=ink)
    return im.resize((w, h), Image.LANCZOS)


def pop_option_image(label, on, w, h):
    S = 2
    im = Image.new("RGBA", (w * S, h * S), ORANGE + (255,) if on else (16, 16, 16, 255))
    d = ImageDraw.Draw(im)
    size = POP_TEXT
    while size > 14 and d.textlength(label, font=font(size * S)) > (w - 16) * S:
        size -= 1
    d.text((w * S / 2.0, h * S / 2.0), label, font=font(size * S), fill=(17, 17, 17) if on else INK, anchor="mm")
    if not on:
        d.line([8 * S, h * S - 1, w * S - 8 * S, h * S - 1], fill=(48, 48, 48), width=S)
    return im.resize((w, h), Image.LANCZOS)


def fix_popups(skin, folder):
    """The framework's pop-up fields, rebuilt (0.1.3):
      - the list's open flag is the engine's pop_<key> (closed on a pick and on every page change), not the wrapper's
        <key>__open, which stayed open across pages and covered the next page's controls, taking their touches;
      - the field itself is a Q-Link focus on the value, as a knob is, so the data wheel and a Q-Link step it; the arrow
        box on its right end opens and closes the list (a Toggle Switch on pop_<key>, the trigger buttons' action);
      - the list's options are redrawn in the panel's font at a readable size."""
    comps = skin.page["componentsData"]
    # the arrow is built like the panel's on/off switches (Mouse Down > Q-Link, and the Button flips the value once):
    # a Toggle Switch action plus the Button's own click flipped it twice per tap, so 0.1.3's lists opened and closed
    tog = next(v for k, v in skin.defs.items() if k.startswith("shToggle"))
    pops = [c for c in spec.CONTROLS if c["kind"] == "enum" and c["widget"] == "popup"]
    remap = {"Parameter %d" % skin.index[c["key"] + "__open"]: "Parameter %d" % skin.index["pop_" + c["key"]] for c in pops}
    remap_ie = {}
    for old, new in remap.items():
        remap_ie["IndexedEnabling/1/2/" + old] = "IndexedEnabling/1/2/" + new
    made = set()
    out = []
    for inst in comps:
        t = inst["componentData"]["type"]
        hs = inst["bounds"].get("additionalInvalidatingHandles", [])
        inst["bounds"]["additionalInvalidatingHandles"] = [remap_ie.get(h, h) for h in hs]
        for m in inst["handle remapping"]["map"]:
            if m["key"] == "Data" and m["value"] in remap and not t.startswith("shPopField"):
                m["value"] = remap[m["value"]]
        out.append(inst)
        if not t.startswith("shPopField"):
            continue
        mp = {m["key"]: m["value"] for m in inst["handle remapping"]["map"]}
        pop = remap[mp["Data"]]
        x, y, w, h = bounds(inst["bounds"]["bounds"])
        fkey = "psPopField_%dx%d" % (w, h)
        if fkey not in skin.defs:
            d = json.loads(json.dumps(skin.defs[t]))
            d["actions"] = [a for a in d["actions"] if a["onAction"] == "Mouse Down"]
            d["actions"][0]["handler"] = "Q-Link"
            for sub in d["componentsData"]:
                if sub["componentData"]["type"] == "Label":
                    sub["bounds"]["bounds"] = bstr(8, 0, w - POP_ARROW_W - 12, h)
            skin.defs_list.append({"key": fkey, "value": d})
            skin.defs[fkey] = d
        inst["componentData"]["type"] = fkey
        inst["handle remapping"]["map"] = [{"key": "Data", "value": mp["Text"]}, {"key": "Text", "value": mp["Text"]}]
        akey = "psPopArrow_%dx%d" % (POP_ARROW_W, h)
        if akey not in skin.defs:
            d = json.loads(json.dumps(tog))
            d["actions"] = [a for a in d["actions"] if a["onAction"] == "Mouse Down"]
            assert d["actions"] and d["actions"][0]["handler"] == "Q-Link", "switch template changed"
            for sub in d["componentsData"]:
                sub["bounds"]["bounds"] = bstr(0, 0, POP_ARROW_W, h)
                if sub["componentData"]["type"] == "Button":
                    sub["componentData"]["data"]["offImage"] = "ps_pop_arrow_%d_off.png" % h
                    sub["componentData"]["data"]["onImage"] = "ps_pop_arrow_%d_on.png" % h
            pop_arrow_image(False, POP_ARROW_W, h).save(os.path.join(folder, "ps_pop_arrow_%d_off.png" % h))
            pop_arrow_image(True, POP_ARROW_W, h).save(os.path.join(folder, "ps_pop_arrow_%d_on.png" % h))
            skin.defs_list.append({"key": akey, "value": d})
            skin.defs[akey] = d
        arrow = json.loads(json.dumps(inst))
        arrow["componentData"]["type"] = akey
        arrow["componentData"]["name"] = inst["componentData"]["name"] + " list"
        arrow["handle remapping"]["map"] = [{"key": "Data", "value": pop}]
        arrow["bounds"]["bounds"] = bstr(x + w - POP_ARROW_W, y, POP_ARROW_W, h)
        arrow["bounds"]["acceptsHWFocus"] = "No"
        out.append(arrow)
        made.add(fkey)
    comps[:] = out
    # option images: shared by identical options, so redraw each image once from the first option that uses it
    done = set()
    for key, d in skin.defs.items():
        m = re.match(r"shPopOpt_\d+_(.+)_(\d+)$", key)
        if not m:
            continue
        label = skin.params[m.group(1)]["options"][int(m.group(2))]
        for sub in d["componentsData"]:
            if sub["componentData"]["type"] != "Button":
                continue
            _, _, w, h = bounds(sub["bounds"]["bounds"])
            data = sub["componentData"]["data"]
            for name, on in ((data["onImage"], True), (data["offImage"], False)):
                if name not in done:
                    done.add(name)
                    pop_option_image(label, on, w, h).save(os.path.join(folder, name))
    # nothing may still point at a wrapper-side <key>__open
    left = [i for i in comps if any(m["value"] in remap for m in i["handle remapping"]["map"]) or
            any(h.split("/")[-1] in remap for h in i["bounds"].get("additionalInvalidatingHandles", []))]
    assert not left, "pop-up parts still on <key>__open: %r" % [i["componentData"]["name"] for i in left]
    return len(made)


# ------------------------------------------------------------------------------------------------ panels
def text(d, xy, s, size, fill=INK, anchor="mm"):
    d.text((xy[0] * SS, xy[1] * SS), s, font=font(size * SS), fill=fill, anchor=anchor)


def knob_scale(d, c):
    cx, cy, R = c["cx"], c["cy"], c["r"]
    for i in range(11):
        a = math.radians(-SWEEP + 2 * SWEEP * i / 10 - 90)
        r0, r1 = R + 7, R + (15 if i in (0, 5, 10) else 11)
        d.line([((cx + math.cos(a) * r0) * SS, (cy + math.sin(a) * r0) * SS),
                ((cx + math.cos(a) * r1) * SS, (cy + math.sin(a) * r1) * SS)], fill=LINE, width=2 * SS)
    lo, hi = c["min"], c["max"]
    fmt = lambda v: ("%+d" % v) if lo < 0 and v != 0 else "%g" % v
    for v, ang in ((lo, -SWEEP), (hi, SWEEP)):
        a = math.radians(ang - 90)
        text(d, (cx + math.cos(a) * (R + 30), cy + math.sin(a) * (R + 26)), fmt(v), 17, DIM)
    if lo < 0 < hi:
        text(d, (cx, cy - R - 24), "0", 17, DIM)


def control_box(c):
    """Top-left, width and height of a control on its page (for labels)."""
    if c["kind"] == "knob":
        return c["cx"] - c["r"], c["cy"] - c["r"], 2 * c["r"], 2 * c["r"]
    if c["kind"] == "enum" and c["widget"] == "enum_h":
        per = int(math.ceil(len(c["options"]) / float(c["rows"])))
        w, h = per * c["sw"], c["rows"] * c["sh"]
        return c["cx"] - w // 2, c["cy"] - h // 2, w, h
    if c["kind"] == "enum":
        return c["cx"] - c["w"] // 2, c["cy"] - c["h"] // 2, c["w"], c["h"]
    if c["kind"] == "toggle":
        return c["cx"] - 42, c["cy"] - 20, 84, 40
    return c["cx"] - 60, c["cy"] - 20, 120, 40


def view_panel(vkey, title):
    im = Image.new("RGB", (W * SS, H * SS), PANEL)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W * SS, 70 * SS], fill=HEADER)
    d.line([0, 70 * SS, W * SS, 70 * SS], fill=LINE, width=2 * SS)
    text(d, (420, 36), title, 30, INK, "lm")
    d.rectangle([8 * SS, 80 * SS, (W - 8) * SS, (H - 6) * SS], outline=(90, 90, 90), width=2 * SS)
    for c in spec.CONTROLS:
        if c["view"] != vkey:
            continue
        x, y, w, h = control_box(c)
        if c["kind"] == "knob":
            knob_scale(d, c)
            ly = y - (48 if c["min"] < 0 < c["max"] else 34)
            text(d, (c["cx"], ly), c["name"].upper(), 22 if c["r"] >= 40 else 18)
        elif c["kind"] == "button":
            pass
        else:
            text(d, (c["cx"], y - 22), c["name"].upper(), 22)
            if c["kind"] == "enum" and c["widget"] == "popup":   # the field MPC writes the choice into
                d.rounded_rectangle([x * SS, y * SS, (x + w) * SS, (y + h) * SS], radius=6 * SS, fill=(18, 18, 18),
                                    outline=(110, 110, 110), width=2 * SS)
                ax, ay = x + w - 22, y + h / 2.0
                d.polygon([((ax - 9) * SS, (ay - 5) * SS), ((ax + 9) * SS, (ay - 5) * SS), (ax * SS, (ay + 7) * SS)],
                          fill=ORANGE)
    if vkey == "patch":
        patch_sockets(d)
    if vkey == "tun":
        text(d, (1125, 250), "SETS THE 12 TUNE KNOBS", 16, DIM)
    return im.resize((W, H), Image.LANCZOS)


def patch_sockets(d):
    ins = {j[0]: j for j in spec.INS}
    outs = {o[0]: o for o in spec.OUTS}
    text(d, (1130, 150), "INPUTS", 26, DIM)
    text(d, (1130, 182), "voltages, triggers", 16, DIM)
    text(d, (1130, 268), "OUTPUTS", 26, DIM)
    text(d, (1130, 296), "one cable each", 16, DIM)
    d.line([20 * SS, 314 * SS, 1260 * SS, 314 * SS], fill=(90, 90, 90), width=2 * SS)
    for key, (x, y) in spec.JACKS.items():
        is_out = key in outs
        lab = outs[key][1] if is_out else ins[key][1]
        trig = (outs[key][2] if is_out else ins[key][2]) == "trig"
        if is_out:   # outputs: label on an inverted plate, as on modular panels
            d.rounded_rectangle([(x - 44) * SS, (y - 58) * SS, (x + 44) * SS, (y + 30) * SS], radius=8 * SS,
                                fill=(58, 58, 58))
        text(d, (x, y - 40), lab, 17, ORANGE if trig else INK)
        r = spec.JACK_R
        d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=(150, 150, 150))
        d.ellipse([(x - r + 4) * SS, (y - r + 4) * SS, (x + r - 4) * SS, (y + r - 4) * SS], fill=(95, 95, 95))
        d.ellipse([(x - 9) * SS, (y - 9) * SS, (x + 9) * SS, (y + 9) * SS], fill=(5, 5, 5))


# ------------------------------------------------------------------------------------------------ cables
def cable_points(p1, p2, n=48, floor=1e9):
    (x1, y1), (x2, y2) = p1, p2
    dist = math.hypot(x2 - x1, y2 - y1)
    sag = 28 + 0.22 * dist
    bow = 0.0
    if abs(x2 - x1) < 0.35 * abs(y2 - y1):   # nearly vertical: swing out sideways, or it would hide behind itself
        bow = (0.18 * abs(y2 - y1) + 20) * (1 if (int(x1) // 7) % 2 else -1) * (dist / max(dist, 1.0))
    low = min(max(y1, y2) + sag, floor)   # never droop off the page
    c1 = (x1 + (x2 - x1) * 0.2 + bow, low)
    c2 = (x2 - (x2 - x1) * 0.2 + bow, low)
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * x1 + b * c1[0] + c * c2[0] + e * x2, a * y1 + b * c1[1] + c * c2[1] + e * y2))
    return pts


def draw_cable(p1, p2, colour, scale=1.0, clip=(0, 0, W, H)):
    """-> (image, x, y) of the cable from p1 to p2 (page coordinates), cropped to what it covers."""
    width, outline, plug = 6.5 * scale, 10 * scale, 11 * scale
    pts = cable_points(p1, p2, floor=clip[3] + (clip[3] - max(p1[1], p2[1])) * 0.33 - 4 * outline)
    m = outline + plug + 2
    x0 = max(clip[0], int(math.floor(min(p[0] for p in pts) - m)))
    y0 = max(clip[1], int(math.floor(min(p[1] for p in pts) - m)))
    x1 = min(clip[2], int(math.ceil(max(p[0] for p in pts) + m)))
    y1 = min(clip[3], int(math.ceil(max(p[1] for p in pts) + m)))
    S = 3
    im = Image.new("RGBA", ((x1 - x0) * S, (y1 - y0) * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    sp = [((x - x0) * S, (y - y0) * S) for x, y in pts]
    dark = tuple(int(v * 0.45) for v in colour)
    d.line(sp, fill=dark + (235,), width=max(1, int(outline * S)), joint="curve")
    d.line(sp, fill=colour + (240,), width=max(1, int(width * S)), joint="curve")
    hl = tuple(min(255, int(v * 1.35) + 30) for v in colour)
    d.line([(x, y - width * S * 0.22) for x, y in sp], fill=hl + (150,), width=max(1, int(width * S * 0.25)))
    for (x, y) in (sp[0], sp[-1]):
        r = plug * S
        d.ellipse([x - r, y - r, x + r, y + r], fill=dark + (255,))
        d.ellipse([x - r * 0.78, y - r * 0.78, x + r * 0.78, y + r * 0.78], fill=colour + (255,))
        d.ellipse([x - r * 0.35, y - r * 0.55, x + r * 0.1, y - r * 0.1], fill=hl + (200,))
    im = im.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    return im, x0, y0


def tile_pieces(im, x0, y0, T):
    """Cut a cable picture along a page-aligned T x T grid and crop each piece to what it covers, so the decoded
    pictures hold the cable and little else (a whole diagonal cable's box is mostly empty). Pieces never overlap."""
    a = im.split()[3]
    out = []
    for gy in range((y0 // T) * T, y0 + im.size[1], T):
        for gx in range((x0 // T) * T, x0 + im.size[0], T):
            bx0, by0 = max(gx, x0) - x0, max(gy, y0) - y0
            bx1, by1 = min(gx + T, x0 + im.size[0]) - x0, min(gy + T, y0 + im.size[1]) - y0
            if bx1 <= bx0 or by1 <= by0:
                continue
            bb = a.crop((bx0, by0, bx1, by1)).getbbox()
            if not bb:
                continue
            l, t, r, b = bx0 + bb[0], by0 + bb[1], bx0 + bb[2], by0 + bb[3]
            out.append((im.crop((l, t, r, b)), x0 + l, y0 + t))
    return out


# ------------------------------------------------------------------------------------------------ compositing
class Composer:
    """Draws the page as MPC would for a given state (param key -> value index or 0..1), from the skin itself."""

    def __init__(self, skin):
        self.skin = skin
        self.cache = {}

    def img(self, name):
        if name not in self.cache:
            self.cache[name] = Image.open(os.path.join(self.skin.dir, name)).convert("RGBA")
        return self.cache[name]

    def shown(self, inst, state):
        for h in inst["bounds"]["additionalInvalidatingHandles"]:
            m = re.match(r"IndexedEnabling/(\d+)/(\d+)/Parameter (\d+)", h)
            if m and state.get(self.skin.keys[int(m.group(3))], 0) != int(m.group(1)):
                return False
        return True

    def norm(self, key, state):
        p = self.skin.params.get(key)
        if key in state:
            v = state[key]
        elif p is not None:
            v = p.get("default", 0)
        else:
            v = 0
        if p is None:
            return 0.0
        if "options" in p:
            n = len(p["options"])
            return v / float(n - 1) if n > 1 else 0.0
        lo, hi = p.get("min", 0), p.get("max", 1)
        return (v - lo) / (hi - lo) if hi > lo else 0.0

    def value(self, key, state):
        p = self.skin.params.get(key)
        if key in state:
            return state[key]
        return p.get("default", 0) if p else 0

    def compose(self, state, skip_images=()):
        page = Image.new("RGBA", (W, H), PANEL + (255,))
        for inst in self.skin.page["componentsData"]:
            if not self.shown(inst, state):
                continue
            x, y, w, h = bounds(inst["bounds"]["bounds"])
            t = inst["componentData"]["type"]
            if t == "Image":
                name = inst["componentData"]["data"]["image"]
                if name and not any(name.startswith(s) for s in skip_images):
                    page.alpha_composite(self.img(name).resize((w, h)) if self.img(name).size != (w, h)
                                         else self.img(name), (x, y))
                continue
            d = self.skin.defs.get(t)
            if not d:
                continue
            key = self.skin.param_of(inst)
            for sub in d["componentsData"]:
                st = sub["componentData"]["type"]
                sx, sy, sw, sh = bounds(sub["bounds"]["bounds"])
                data = sub["componentData"].get("data", {})
                if st == "Knob" and data.get("filmStrip"):
                    strip = self.img(data["filmStrip"])
                    F = strip.size[0]
                    fr = int(round(self.norm(key, state) * 127))
                    page.alpha_composite(strip.crop((0, fr * F, F, fr * F + F)).resize((sw, sh)), (x + sx, y + sy))
                elif st == "Button":
                    if sub["bounds"].get("whenVisible") == "WhenFocussed":
                        continue
                    n = data.get("numButtonsInGroup", 1)
                    v = self.value(key, state)
                    on = (int(round(v)) == data.get("buttonId", 0)) if n > 1 else bool(round(v)) and not \
                        (self.skin.params.get(key, {}).get("momentary"))
                    name = data.get("onImage") if on else data.get("offImage")
                    if name:
                        im = self.img(name)
                        page.alpha_composite(im.resize((sw, sh)) if im.size != (sw, sh) else im, (x + sx, y + sy))
                elif st == "Image" and data.get("image"):
                    page.alpha_composite(self.img(data["image"]).resize((sw, sh)), (x + sx, y + sy))
        return page


# ------------------------------------------------------------------------------------------------ main
def main():
    folder = sys.argv[1]
    preview = None
    if "--preview" in sys.argv:
        preview = sys.argv[sys.argv.index("--preview") + 1]
    skin = Skin(folder)
    vidx = skin.index["view"]
    nviews = len(spec.VIEWS)
    comps = skin.page["componentsData"]

    # 1) drop the framework's per-mode backgrounds, keep the plain base
    comps[:] = [c for c in comps if not (c["componentData"]["type"] == "Image" and
                                         c["componentData"]["data"].get("image", "").startswith("sh_mode_"))]
    for name in os.listdir(folder):
        if name.startswith("sh_mode_"):
            os.remove(os.path.join(folder, name))
    Image.new("RGB", (W, H), PANEL).save(os.path.join(folder, "sh_bg_0.png"))

    # 2) knobs, switches, buttons
    radii = write_knob_strips(skin)
    for key, d in skin.defs.items():   # the value under the knob, below the printed scale's end numbers
        if key.startswith("shKnob"):
            for sub in d["componentsData"]:
                x, y, w, h = bounds(sub["bounds"]["bounds"])
                if sub["componentData"]["type"] == "Label":
                    sub["bounds"]["bounds"] = bstr(x, y + 22, w, h)
                elif sub["componentData"]["type"] == "Focus":
                    sub["bounds"]["bounds"] = bstr(x, y, w, h + 22)
    for inst in comps:
        if inst["componentData"]["type"].startswith("shKnob"):
            x, y, w, h = bounds(inst["bounds"]["bounds"])
            inst["bounds"]["bounds"] = bstr(x, y, w, h + 22)
    for key, d in skin.defs.items():
        if key.startswith("shToggle"):
            d["componentsData"] = [s for s in d["componentsData"] if s["componentData"]["type"] != "Label"]
            for s in d["componentsData"]:
                if s["componentData"]["type"] == "Focus":
                    s["bounds"]["bounds"] = bstr(0, 0, 130, 48)
                if s["componentData"]["type"] == "Button":
                    s["bounds"]["bounds"] = bstr(23, 4, 84, 40)
                    s["componentData"]["data"]["onImage"] = "ps_switch_on.png"
                    s["componentData"]["data"]["offImage"] = "ps_switch_off.png"
    switch_image(True).save(os.path.join(folder, "ps_switch_on.png"))
    switch_image(False).save(os.path.join(folder, "ps_switch_off.png"))
    for c in spec.CONTROLS:
        if c["kind"] == "toggle":
            for inst in skin.instances(c["key"]):
                inst["bounds"]["bounds"] = bstr(c["cx"] - 65, c["cy"] - 24, 130, 48)

    def restyle_trigger(prefix, w, h, off_img, on_img, place):
        for key, d in skin.defs.items():
            if not key.startswith(prefix):
                continue
            d["componentsData"] = [s for s in d["componentsData"] if s["componentData"]["type"] != "Label"]
            for s in d["componentsData"]:
                s["bounds"]["bounds"] = bstr(0, 0, w, h)
                if s["componentData"]["type"] == "Button":
                    s["componentData"]["data"]["offImage"] = off_img
                    s["componentData"]["data"]["onImage"] = on_img
        for inst in comps:
            if inst["componentData"]["type"].startswith(prefix):
                inst["bounds"]["bounds"] = bstr(*place(inst))

    navpos = {k: (x, y) for k, _, x, y in spec.NAV}
    navsize = {"nav_zoom": (150, 52), "nav_prev": (90, 52), "nav_next": (90, 52)}
    for k, lbl, _, _ in spec.NAV:
        w, h = navsize[k]
        nav_image(lbl, False, w, h).save(os.path.join(folder, "ps_%s_off.png" % k))
        nav_image(lbl, True, w, h).save(os.path.join(folder, "ps_%s_on.png" % k))
        restyle_trigger("shTrig_%s_" % k, w, h, "ps_%s_off.png" % k, "ps_%s_on.png" % k,
                        lambda inst, k=k, w=w, h=h: (navpos[k][0] - w // 2, navpos[k][1] - h // 2, w, h))
    mt = spec.CTRL["manual_trg1"]
    nav_image("MANUAL TRG 1", False, 210, 52).save(os.path.join(folder, "ps_mtrg_off.png"))
    nav_image("MANUAL TRG 1", True, 210, 52).save(os.path.join(folder, "ps_mtrg_on.png"))
    restyle_trigger("shTrig_manual_trg1_", 210, 52, "ps_mtrg_off.png", "ps_mtrg_on.png",
                    lambda inst: (mt["cx"] - 105, mt["cy"] - 26, 210, 52))
    blank(4, 4).save(os.path.join(folder, "ps_blank.png"))
    jack_press().save(os.path.join(folder, "ps_jack_press.png"))
    for j in spec.OUTS + spec.INS:
        x, y = spec.JACKS[j[0]]
        restyle_trigger("shTrig_tap_%s_" % j[0], 68, 68, "ps_blank.png", "ps_jack_press.png",
                        lambda inst, x=x, y=y: (x - 34, y - 34, 68, 68))
    for v in spec.VIEWS[1:]:
        tx, ty, tw, th = spec.TILES[v[0]]
        tile_highlight(tw, th).save(os.path.join(folder, "ps_tile_on_%s.png" % v[0]))
        restyle_trigger("shTrig_go_%s_" % v[0], tw, th, "ps_blank.png", "ps_tile_on_%s.png" % v[0],
                        lambda inst, tx=tx, ty=ty, tw=tw, th=th: (tx, ty, tw, th))

    fix_popups(skin, folder)

    # 3) view panels (drawn after the controls are final, so the overview can compose them)
    injected = []
    for i, v in enumerate(spec.VIEWS):
        if i == 0:
            continue
        view_panel(v[0], v[1]).save(os.path.join(folder, "ps_view_%d.png" % i))
        injected.append(image_instance("Panel", "ps_view_%d.png" % i, 0, 0, W, H,
                                       ["IndexedEnabling/%d/%d/Parameter %d" % (i, nviews, vidx)]))
    gt = spec.CTRL["geg_trigger"]
    led_xy = (gt["cx"] + 100, gt["cy"] - gt["rows"] * gt["sh"] // 2 - 22)
    led_image(False).save(os.path.join(folder, "ps_led_off.png"))
    led_image(True).save(os.path.join(folder, "ps_led_on.png"))
    gi = spec.VIEW_KEYS.index("geg")
    injected.append(image_instance("LED", "ps_led_off.png", led_xy[0] - 11, led_xy[1] - 11, 22, 22,
                                   ["IndexedEnabling/%d/%d/Parameter %d" % (gi, nviews, vidx)]))
    injected.append(image_instance("LED", "ps_led_on.png", led_xy[0] - 11, led_xy[1] - 11, 22, 22,
                                   ["IndexedEnabling/1/2/Parameter %d" % skin.index["geg_led"]]))
    comps[1:1] = injected   # right after the base background: under every control

    # the overview: each tile is its page in miniature, composed from the skin at the default settings
    composer = Composer(skin)
    TH_MAP = {}
    ov = Image.new("RGB", (W * SS, H * SS), PANEL)
    d = ImageDraw.Draw(ov)
    d.rectangle([0, 0, W * SS, 70 * SS], fill=HEADER)
    d.line([0, 70 * SS, W * SS, 70 * SS], fill=LINE, width=2 * SS)
    text(d, (24, 36), "PS3100XXL", 34, INK, "lm")
    text(d, (250, 38), "POLYPHONIC SYNTHESIZER", 20, DIM, "lm")
    text(d, (1262, 36), "TAP A SECTION TO ZOOM IN", 20, DIM, "rm")
    ov = ov.resize((W, H), Image.LANCZOS)
    for i, v in enumerate(spec.VIEWS):
        if i == 0:
            continue
        tx, ty, tw, th = spec.TILES[v[0]]
        page = composer.compose({"view": i}, skip_images=("ps_led_on",)).convert("RGB")
        thumb = page.crop((0, 72, W, H))
        band = 28
        s = min((tw - 4) / float(thumb.size[0]), (th - band - 2) / float(thumb.size[1]))
        tim = thumb.resize((max(1, int(thumb.size[0] * s)), max(1, int(thumb.size[1] * s))), Image.LANCZOS)
        ov.paste(tim, (tx + (tw - tim.size[0]) // 2, ty + band + (th - band - tim.size[1]) // 2))
        TH_MAP[v[0]] = (tx + (tw - tim.size[0]) // 2, ty + band + (th - band - tim.size[1]) // 2, s)
        dd = ImageDraw.Draw(ov)
        dd.rectangle([tx, ty, tx + tw - 1, ty + th - 1], outline=(110, 110, 110), width=2)
        dd.rectangle([tx + 2, ty + 2, tx + tw - 3, ty + 27], fill=HEADER)
        dd.text((tx + 10, ty + 14), v[2], font=font(18), fill=ORANGE, anchor="lm")
    sx, sy, sw, sh = spec.TILES["setup"]
    dd = ImageDraw.Draw(ov)
    bx = sx + sw + 6
    dd.rectangle([bx, sy, W - 2, sy + sh - 1], fill=HEADER, outline=(110, 110, 110), width=2)
    dd.text(((bx + W) // 2, sy + 42), "L'Cronx", font=font(30), fill=INK, anchor="mm")
    dd.text(((bx + W) // 2, sy + 84), "after the Korg PS-3100", font=font(18), fill=DIM, anchor="mm")
    tx, ty, tw, th = spec.TILES["patch"]
    hx = tx + tw + 30
    lines = ["Tap a section to work on it.", "OVERVIEW comes back here,", "< > step through the sections.", "",
             "PATCH BAY: tap an output,", "then an input, to patch.", "Tap a patched output to unplug it.",
             "Q-Links follow the section", "on screen."]
    for k, ln in enumerate(lines):
        dd.text((hx, ty + 20 + k * 30), ln, font=font(22), fill=DIM if ln else DIM, anchor="lm")
    ov.save(os.path.join(folder, "ps_view_0.png"))
    comps.insert(1, image_instance("Panel", "ps_view_0.png", 0, 0, W, H,
                                   ["IndexedEnabling/0/%d/Parameter %d" % (nviews, vidx)]))

    # 4) cables: patch page and overview copies, one picture per output and reachable input; held rings.
    # Each is switched by a small parameter (spec.cable_param / held_param: at most JACK_GROUP + 1 positions, 0.1.4).
    pos = dict(spec.JACKS)
    px0, py0, ps = TH_MAP["patch"]
    cable_insts, total_px = [], 0
    pieces = 0
    for oi, o in enumerate(spec.OUTS):
        ins = [j for j in spec.INS if j[2] == o[2]]
        colour = spec.CABLE_COLOURS[oi % len(spec.CABLE_COLOURS)]
        for t, j in enumerate(ins):
            ov_map = lambda p: (px0 + p[0] * ps, py0 + (p[1] - 72) * ps)
            for tag, prefix, scale, mp, clip in (
                    ("p", "cp", 1.0, lambda p: p, (0, 72, W, H)),
                    ("o", "co", ps, ov_map, (tx, ty, tx + tw, ty + th))):
                key, opt, nopt = spec.cable_param(prefix, o, j)
                im, x0, y0 = draw_cable(mp(pos[o[0]]), mp(pos[j[0]]), colour, scale, clip=clip)
                handle = ["IndexedEnabling/%d/%d/Parameter %d" % (opt, nopt, skin.index[key])]
                for k, (piece, px, py) in enumerate(tile_pieces(im, x0, y0, spec.CABLE_TILE)):
                    name = "ps_cab_%s_%s_%s_%d.png" % (tag, o[0], j[0], k)
                    piece.save(os.path.join(folder, name), optimize=True)
                    total_px += piece.size[0] * piece.size[1]
                    pieces += 1
                    cable_insts.append(image_instance("Cable", name, px, py, piece.size[0], piece.size[1], handle))
    ring_image().save(os.path.join(folder, "ps_held.png"))
    for j in spec.INS:   # an input tapped first waits for its output
        x, y = pos[j[0]]
        key, opt, nopt = spec.held_in_param(j)
        cable_insts.append(image_instance("Held", "ps_held.png", x - 33, y - 33, 66, 66,
                                          ["IndexedEnabling/%d/%d/Parameter %d" % (opt, nopt, skin.index[key])]))
    for o in spec.OUTS:
        x, y = pos[o[0]]
        key, opt, nopt = spec.held_param(o)
        cable_insts.append(image_instance("Held", "ps_held.png", x - 33, y - 33, 66, 66,
                                          ["IndexedEnabling/%d/%d/Parameter %d" % (opt, nopt, skin.index[key])]))
    at = 1 + len(injected) + 1
    comps[at:at] = cable_insts
    skin.save()

    print("post_skin: %d views, knob radii %s, %d cable pieces (%.1f MB decoded), %d components" % (
        nviews, radii, pieces, total_px * 4 / 1e6, len(comps)))

    if preview:
        os.makedirs(preview, exist_ok=True)
        demo = {"geg": "sg_frq", "mg1": "lp_frq", "vp1": "vca2", "trg1": "geg_trg", "mw": "mg_amt", "add": "j1_in"}
        for i, v in enumerate(spec.VIEWS):
            st = {"view": i, "in_sec": 1 if i else 0}
            for oi, o in enumerate(spec.OUTS):
                if o[0] in demo and (v[0] == "patch" or i == 0):
                    j = next(x for x in spec.INS if x[0] == demo[o[0]])
                    key, opt, _ = spec.cable_param("cp" if v[0] == "patch" else "co", o, j)
                    st[key] = opt
            if v[0] == "patch":
                key, opt, _ = spec.held_param(next(o for o in spec.OUTS if o[0] == "sh"))
                st[key] = opt
            composer.compose(st).convert("RGB").save(os.path.join(preview, "view_%02d_%s.png" % (i, v[0])))


if __name__ == "__main__":
    main()
