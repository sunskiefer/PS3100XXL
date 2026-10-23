#!/usr/bin/env python3
"""Checks the built skin against tools/spec.py, the inventory: nothing in the list may be missing from the panel.

    python3 tools/check_skin.py "<skin dir>/Plugin Skins"

- every control is on its section's page (a component bound to its parameter, shown only on that view);
- every jack has its touch area on the patch page, at its place;
- every jack is one touch zone on its socket (no overlaps); every patch step has its picture and buttons;
- every section has its overview tile and its panel picture; navigation is on every zoomed page;
- every image the skin names exists.
Exit status 1 with a list of what is missing.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_skin as P  # noqa: E402
import spec  # noqa: E402


def main():
    folder = sys.argv[1]
    skin = P.Skin(folder)
    vidx = skin.index["view"]
    nv = len(spec.VIEWS)
    problems = []
    by_param = {}
    images = set()
    for inst in skin.page["componentsData"]:
        hs = inst["bounds"]["additionalInvalidatingHandles"]
        for m in inst["handle remapping"]["map"]:   # Data (knobs, buttons) and Text (a popup field shows its option)
            if m["value"].startswith("Parameter "):
                by_param.setdefault(skin.keys[int(m["value"].split()[1])], []).append((inst, hs))
        if inst["componentData"]["type"] == "Image":
            images.add(inst["componentData"]["data"]["image"])
    for d in skin.defs.values():
        for sub in d.get("componentsData", []):
            data = sub["componentData"].get("data", {})
            for key in ("image", "onImage", "offImage", "filmStrip"):
                if data.get(key):
                    images.add(data[key])

    def on_view(key, view):
        want = "IndexedEnabling/%d/%d/Parameter %d" % (spec.VIEW_KEYS.index(view), nv, vidx)
        return any(want in hs for _, hs in by_param.get(key, []))

    for c in spec.CONTROLS:
        if not on_view(c["key"], c["view"]):
            problems.append("control %s (%s) is not on the %s page" % (c["key"], c["name"], c["view"]))
    tiles = "IndexedEnabling/1/2/Parameter %d" % skin.index["pk_t"]
    for j in spec.OUTS + spec.INS:
        k = "tap_" + j[0]
        insts = by_param.get(k, [])
        if len(insts) != 1 or tiles not in insts[0][1]:
            problems.append("jack %s: %d tile(s), want one shown on the patch steps (pk_t)" % (j[1], len(insts)))
        else:
            if tuple(P.bounds(insts[0][0]["bounds"]["bounds"])) != spec.pick_box(j[0]):
                problems.append("jack %s: its touch zone is not on its socket" % j[1])
            if skin.defs[insts[0][0]["componentData"]["type"]]["actions"][0]["handler"] != "Toggle Switch":
                problems.append("jack %s: not a trigger button like the page tiles" % j[1])
    # no tile overlaps another, and all stay inside the page below the header
    boxes = [spec.pick_box(k) for k in spec.PICK_ORDER]
    for a in range(len(boxes)):
        ax, ay, aw, ah = boxes[a]
        if ay < 72 or ay + ah > P.H or ax < 0 or ax + aw > P.W:
            problems.append("tile %s is off the page" % spec.PICK_ORDER[a])
        for b in range(a + 1, len(boxes)):
            bx, by, bw, bh = boxes[b]
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                problems.append("tiles %s and %s overlap" % (spec.PICK_ORDER[a], spec.PICK_ORDER[b]))
    for key, shown in (("pk_cancel", "IndexedEnabling/1/2/Parameter %d" % skin.index["pk_c"]),
                       ("pk_unplug", "IndexedEnabling/6/%d/Parameter %d" % (len(spec.PK_STEPS), skin.index["pk"])),
                       ("pk_done", "IndexedEnabling/6/%d/Parameter %d" % (len(spec.PK_STEPS), skin.index["pk"]))):
        insts = by_param.get(key, [])
        if len(insts) != 1 or shown not in insts[0][1]:
            problems.append("%s: want one button shown by %s" % (key, shown))
    for v in spec.VIEWS[1:]:
        if not on_view("go_" + v[0], "overview"):
            problems.append("no overview tile for %s" % v[0])
    # navigation: one instance per button, shown on every section page (in_sec), never one copy per page: a press that
    # changes the page must not swap the button under the finger for another page's copy
    sec = "IndexedEnabling/1/2/Parameter %d" % skin.index["in_sec"]
    for k, _, _, _ in spec.NAV:
        insts = by_param.get(k, [])
        if len(insts) != 1 or sec not in insts[0][1]:
            problems.append("%s: %d instance(s), want one shown on every section page" % (k, len(insts)))
    # pop-up lists: opened by the engine's pop_<key> (closed on a page change), the field a Q-Link focus on the value
    for c in spec.CONTROLS:
        if c["kind"] != "enum" or c["widget"] != "popup":
            continue
        pidx = skin.index["pop_" + c["key"]]
        if by_param.get(c["key"] + "__open"):
            problems.append("pop-up %s still bound to the wrapper's %s__open" % (c["key"], c["key"]))
        arrows = by_param.get("pop_" + c["key"], [])
        if not arrows:
            problems.append("pop-up %s has no arrow on pop_%s" % (c["key"], c["key"]))
        for inst, _ in arrows:
            acts = [a["onAction"] + ">" + a["handler"] for a in skin.defs[inst["componentData"]["type"]]["actions"]]
            if any(a.endswith("Toggle Switch") for a in acts):
                problems.append("pop-up %s arrow flips twice per tap (%s)" % (c["key"], acts))
        opened = "IndexedEnabling/1/2/Parameter %d" % pidx
        parts = [hs for (_, hs) in by_param.get(c["key"], []) if opened in hs]
        if len(parts) != len(c["options"]):
            problems.append("pop-up %s: %d options shown by pop_%s, want %d" % (c["key"], len(parts), c["key"],
                                                                                 len(c["options"])))
    for i in range(nv):
        if "ps_view_%d.png" % i not in images:
            problems.append("no panel picture for view %d" % i)
    # cables and rings: every (output, input) picture on the patch page and the overview, each switched by a small
    # parameter (at most 11 positions: nothing larger has been seen working on a Force; 0.1.4)
    handles = set()
    for inst in skin.page["componentsData"]:
        for h in inst["bounds"]["additionalInvalidatingHandles"]:
            m = re.match(r"IndexedEnabling/(\d+)/(\d+)/Parameter (\d+)$", h)
            if m:
                handles.add(h)
                if int(m.group(2)) > 11:
                    problems.append("%s: %s positions (more than the 11 seen working)" % (h, m.group(2)))
    for k in range(1, len(spec.PK_STEPS)):
        if "ps_pick_%d.png" % k not in images:
            problems.append("no picture for patch step %d" % k)
        if "IndexedEnabling/%d/%d/Parameter %d" % (k, len(spec.PK_STEPS), skin.index["pk"]) not in handles:
            problems.append("patch step %d's picture is not switched by pk" % k)
    for name in sorted(images):
        if not os.path.exists(os.path.join(folder, name)):
            problems.append("image %s is missing" % name)
    if problems:
        print("check_skin: %d problems" % len(problems))
        for p in problems:
            print("  " + p)
        sys.exit(1)
    print("check_skin: OK -- %d controls, %d jacks, %d sections, every patch step drawn, %d images" % (
        len(spec.CONTROLS), len(spec.JACKS), nv - 1, len(images)))


if __name__ == "__main__":
    main()
