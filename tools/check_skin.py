#!/usr/bin/env python3
"""Checks the built skin against tools/spec.py, the inventory: nothing in the list may be missing from the panel.

    python3 tools/check_skin.py "<skin dir>/Plugin Skins"

- every control is on its section's page (a component bound to its parameter, shown only on that view);
- every jack has its touch area on the patch page, at its place;
- every output has a cable picture for every input it can reach, on the patch page and on the overview;
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
    for j in spec.OUTS + spec.INS:
        k = "tap_" + j[0]
        if not on_view(k, "patch"):
            problems.append("jack %s has no touch area on the patch page" % j[1])
        else:
            x, y = spec.JACKS[j[0]]
            bx, by, bw, bh = P.bounds(by_param[k][0][0]["bounds"]["bounds"])
            if not (bx < x < bx + bw and by < y < by + bh):
                problems.append("jack %s's touch area is not on its socket" % j[1])
    for v in spec.VIEWS[1:]:
        if not on_view("go_" + v[0], "overview"):
            problems.append("no overview tile for %s" % v[0])
        for k, _, _, _ in spec.NAV:
            if not on_view(k, v[0]):
                problems.append("%s missing on the %s page" % (k, v[0]))
    for i in range(nv):
        if "ps_view_%d.png" % i not in images:
            problems.append("no panel picture for view %d" % i)
    for o in spec.OUTS:
        ins = [j for j in spec.INS if j[2] == o[2]]
        nopt = 1 + 2 * len(ins)
        cidx = skin.index["cab_" + o[0]]
        shown = set()
        for inst in skin.page["componentsData"]:
            for h in inst["bounds"]["additionalInvalidatingHandles"]:
                m = re.match(r"IndexedEnabling/(\d+)/(\d+)/Parameter (\d+)$", h)
                if m and int(m.group(3)) == cidx:
                    if int(m.group(2)) != nopt:
                        problems.append("cable %s: option count %s, parameter has %d" % (o[0], m.group(2), nopt))
                    shown.add(int(m.group(1)))
        missing = set(range(1, nopt)) - shown
        if missing:
            problems.append("cable %s: no picture for options %s" % (o[0], sorted(missing)))
    for name in sorted(images):
        if not os.path.exists(os.path.join(folder, name)):
            problems.append("image %s is missing" % name)
    if problems:
        print("check_skin: %d problems" % len(problems))
        for p in problems:
            print("  " + p)
        sys.exit(1)
    print("check_skin: OK -- %d controls, %d jacks, %d sections, every cable drawn, %d images" % (
        len(spec.CONTROLS), len(spec.JACKS), nv - 1, len(images)))


if __name__ == "__main__":
    main()
