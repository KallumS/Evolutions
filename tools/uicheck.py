#!/usr/bin/env python3
"""
Checks Midi Evolver's window against the house rules - Apple's HIG
Foundations as the family applies them (decision 0006) - by running the real
@gfx code headlessly in ysfx, and the helper's side of the shared memory.
AutoCC's checker (tools/uicheck.py there), with Midi Evolver's controls.

    tools/build_host.sh                 # once: builds tools/build/host
    python3 tools/uicheck.py            # static checks, then the window
    python3 tools/uicheck.py --static   # static checks only (no build needed)
    python3 tools/uicheck.py --shots DIR    # also write PNG screenshots
    python3 tools/uicheck.py --jsfx copy.jsfx   # check another copy (tools/bite.py)

How it sees the window: a copy of the plug-in is made in a temporary folder
with every gfx_drawstr, gfx_rect and gfx_line in @gfx routed through a small
logger, which writes each string's box, its colour and the pixels under it,
and each rectangle and line, into memory the host reads back. Two hooks let
it write one gmem slot a frame (as the helper would) and copy gmem into
memory. Nothing in the shipped file is changed.

Every check prints PASS or FAIL; the script exits non-zero if any failed.
Nothing here has been run inside REAPER.
"""

import argparse
import collections
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

FAILS = []
PASSES = []


def check(ok, name, detail=""):
    (PASSES if ok else FAILS).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (("  -  " + detail) if detail and not ok else ""))
    return ok


# ---------------------------------------------------------------- the source
def sections(text):
    out, name, order = {}, "header", ["header"]
    for line in text.split("\n"):
        m = re.match(r"^@(\w+)", line)
        if m:
            name = m.group(1)
            order.append(name)
            out[name] = [line]
            continue
        out.setdefault(name, []).append(line)
    return {k: "\n".join(v) for k, v in out.items()}, order


def colours(text):
    return {m.group(1): int(m.group(2), 16) for m in re.finditer(r"\b(C_\w+)\s*=\s*0x([0-9A-Fa-f]{6})\s*;", text)}


def strip_code(src):
    """The source with strings and // comments blanked, so brackets can be counted."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            out.append('"' + " " * (j - i - 1) + '"')
            i = j + 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def call_args(clean, start):
    """For a call whose '(' is at start: (index of the matching ')', number of arguments)."""
    depth, args, i = 0, 1, start
    while i < len(clean):
        c = clean[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i, args
        elif c == "," and depth == 1:
            args += 1
        i += 1
    raise ValueError("unbalanced call at %d" % start)


WRAP = r"""
// ---- uicheck instrumentation (only in the checked copy) ----
T_LOG = 3000000; T_W = 160; t_n = 0;
function t_text(s, f, r, b, na) local(w, h, x0, y0, bx, by, p, j, sx, sy, pr, pg, pb, n, k, rr, gg, bb, aa) (
  gfx_measurestr(s, w, h);
  x0 = gfx_x; y0 = gfx_y; bx = x0; by = y0;
  na >= 4 ? (
    (f & 1) ? ( bx = x0 + (r - x0 - w) / 2 ) : (f & 2) ? ( bx = r - w );
    (f & 4) ? ( by = y0 + (b - y0 - h) / 2 ) : (f & 8) ? ( by = b - h );
  );
  p = T_LOG + t_n * T_W;
  p[0] = 1; p[1] = bx; p[2] = by; p[3] = w; p[4] = h;
  p[5] = gfx_r; p[6] = gfx_g; p[7] = gfx_b; p[8] = gfx_a;
  p[9] = na >= 4 ? r - x0 : -1; p[10] = na >= 4 ? b - y0 : -1; p[11] = gfx_texth;
  rr = gfx_r; gg = gfx_g; bb = gfx_b; aa = gfx_a;
  j = 0;
  loop(5,
    sx = j == 0 ? bx + w / 2 : (j == 1 || j == 3) ? bx + 1 : bx + w - 2;
    sy = j == 0 ? by + h / 2 : j < 3 ? by + 2 : by + h - 3;
    gfx_x = floor(sx); gfx_y = floor(sy);
    gfx_getpixel(pr, pg, pb);
    p[12 + j] = floor(pr * 255 + 0.5) * 65536 + floor(pg * 255 + 0.5) * 256 + floor(pb * 255 + 0.5);
    j += 1;
  );
  gfx_r = rr; gfx_g = gg; gfx_b = bb; gfx_a = aa;
  n = min(strlen(s), 140); p[17] = n; k = 0;
  loop(n, p[18 + k] = str_getchar(s, k); k += 1; );
  t_n += 1;
  gfx_x = x0; gfx_y = y0;
);
function t_drawstr1(s) ( t_text(s, 0, 0, 0, 1); gfx_drawstr(s); );
function t_drawstr2(s, f) ( t_text(s, f, 0, 0, 2); gfx_drawstr(s, f); );
function t_drawstr4(s, f, r, b) ( t_text(s, f, r, b, 4); gfx_drawstr(s, f, r, b); );
function t_rect(x, y, w, h, f) local(p) (
  p = T_LOG + t_n * T_W;
  p[0] = 2; p[1] = x; p[2] = y; p[3] = w; p[4] = h;
  p[5] = gfx_r; p[6] = gfx_g; p[7] = gfx_b; p[8] = gfx_a; p[9] = f;
  t_n += 1;
  gfx_rect(x, y, w, h, f);
);
// Keys reach the window as REAPER documents them ('up' is 30064, Tab 9...),
// with Shift in mouse_cap even when no button is down. ysfx packs the arrow
// codes the other way round and reports Shift only during a click, so the
// checker hands them in here instead.
// A line: its ends, colour and the pixel under its middle before it is drawn.
function t_line(x1, y1, x2, y2) local(p, pr, pg, pb, rr, gg, bb, aa) (
  p = T_LOG + t_n * T_W;
  p[0] = 3; p[1] = x1; p[2] = y1; p[3] = x2; p[4] = y2;
  p[5] = gfx_r; p[6] = gfx_g; p[7] = gfx_b; p[8] = gfx_a;
  rr = gfx_r; gg = gfx_g; bb = gfx_b; aa = gfx_a;
  gfx_x = floor((x1 + x2) / 2); gfx_y = floor((y1 + y2) / 2);
  gfx_getpixel(pr, pg, pb);
  p[9] = floor(pr * 255 + 0.5) * 65536 + floor(pg * 255 + 0.5) * 256 + floor(pb * 255 + 0.5);
  gfx_r = rr; gfx_g = gg; gfx_b = bb; gfx_a = aa;
  t_n += 1;
  gfx_line(x1, y1, x2, y2);
);
function t_getchar() local(k) ( k = t_key; t_key = 0; k ? k : gfx_getchar(); );
function t_rect4(x, y, w, h) ( t_rect(x, y, w, h, 1); );
function t_rect5(x, y, w, h, f) ( t_rect(x, y, w, h, f); );
"""


# The checker's own hands on the shared memory: one gmem slot written a frame
# (as the helper would), and gmem copied into memory the host can read.
HOOKS = """
t_gw_i > 0 ? ( gmem[t_gw_i] = t_gw_v; t_gw_i = 0; );
t_gm_n > 0 ? ( t_k = 0; loop(t_gm_n, (6000000)[t_k] = gmem[t_k]; t_k += 1; ); );
"""


def instrument(text):
    secs, order = sections(text)
    g = secs["gfx"]
    clean = strip_code(g)
    edits = []
    for name in ("gfx_drawstr", "gfx_rect", "gfx_line"):
        for m in re.finditer(r"(?<![\w.])" + name + r"\(", clean):
            _, n = call_args(clean, m.end() - 1)
            if name == "gfx_drawstr" and n not in (1, 2, 4):
                raise ValueError("gfx_drawstr with %d arguments" % n)
            if name == "gfx_rect" and n not in (4, 5):
                raise ValueError("gfx_rect with %d arguments" % n)
            if name == "gfx_line" and n != 4:
                raise ValueError("gfx_line with %d arguments" % n)
            new = {"gfx_drawstr": "t_drawstr%d(" % n, "gfx_rect": "t_rect%d(" % n, "gfx_line": "t_line("}[name]
            edits.append((m.start(), m.end(), new))
    for a, b, new in sorted(edits, reverse=True):
        g = g[:a] + new + g[b:]
    g = re.sub(r"(?<![\w.])gfx_getchar\(\)", "t_getchar()", g)
    first, rest = g.split("\n", 1)
    secs["gfx"] = (first + "\nt_n = 0;\nmouse_cap |= t_mods;\n" + HOOKS + rest)
    first, rest = secs["init"].split("\n", 1)
    secs["init"] = first + "\n" + WRAP + "\n" + rest
    return "\n".join(secs[k] for k in order)


# ---------------------------------------------------------------- colour maths
def lum(c):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c >> 16 & 255) + 0.7152 * f(c >> 8 & 255) + 0.0722 * f(c & 255)


def ratio(a, b):
    x, y = sorted((lum(a), lum(b)))
    return (y + 0.05) / (x + 0.05)


def mix(fg, bg, a):
    out = 0
    for s in (16, 8, 0):
        out = out * 256 + int(round((fg >> s & 255) * a + (bg >> s & 255) * (1 - a)))
    return out



# ---------------------------------------------------------------- the host
class Frame:
    def __init__(self, texts, rects, focus, vars_, lines=()):
        self.texts, self.rects, self.focus, self.v, self.lines = texts, rects, focus, vars_, lines


class UI:
    VARS = ("ui_s ui_zoom focus_id fl_n focus_base FOCUS_W top_h scroll content_h gfx_w gfx_h "
            "status_on vx vy vw vh ey eh rec_on take_ready helper_on waiting req_id holding").split()

    def __init__(self, host, jsfx, w=860, h=780, scale=1):
        self.p = subprocess.Popen([host, jsfx], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, bufsize=1)
        self.send("size %d %d %g" % (w, h, scale), "mouse -1 -1 0 0 0", "frame", "frame")

    def send(self, *lines):
        for l in lines:
            self.p.stdin.write(l + "\n")
        self.p.stdin.write("sync\n")
        self.p.stdin.flush()
        out = []
        while True:
            l = self.p.stdout.readline()
            if not l:
                raise RuntimeError("host stopped: " + self.p.stderr.read())
            l = l.rstrip("\n")
            if l == "SYNC":
                return out
            out.append(l)

    def var(self, *names):
        out = self.send("var " + " ".join(names))
        return {k: float(v) for k, v in (kv.split("=") for kv in out[-1].split()[1:])}

    def frame(self, n=1):
        for _ in range(n):
            self.send("frame")

    KEYS = {"tab": 9, "ret": 13, "space": 32, "esc": 27, "up": 30064, "down": 1685026670,
            "left": 1818584692, "right": 1919379572}

    def key(self, k, mods=0):
        """One key, as REAPER's gfx_getchar() returns it; mods 1 is Shift."""
        self.send("setvar t_key %d" % self.KEYS[k], "setvar t_mods %d" % (8 if mods & 1 else 0), "frame",
                  "setvar t_mods 0", "mouse -1 -1 0 0 0", "frame")

    def look(self):
        """Runs one frame and reads back everything it drew."""
        out = self.send("frame", "log", "var " + " ".join(self.VARS))
        out = [l for l in out if not l.startswith("MIDI ") and l != "ENDMIDI"]
        v = {k: float(x) for k, x in (kv.split("=") for kv in out[-1].split()[1:])}
        n, W = int(v["fl_n"]), int(v["FOCUS_W"])
        mem = self.send("mem %d %d" % (int(v["focus_base"]), max(1, n * W)))[-1].split()[1:]
        mem = [float(x) for x in mem]
        focus = [dict(id=int(mem[i * W]), x=mem[i * W + 1], y=mem[i * W + 2], w=mem[i * W + 3],
                      h=mem[i * W + 4], kind=int(mem[i * W + 5])) for i in range(n)]
        texts, rects, lines = [], [], []
        for l in out:
            if not l.startswith("LOG "):
                continue
            p = [float(x) for x in l.split()[1:]]
            col = int(round(p[5] * 255)) * 65536 + int(round(p[6] * 255)) * 256 + int(round(p[7] * 255))
            if p[0] == 1:
                n_ = int(p[17])
                s = bytes(int(c) & 255 for c in p[18:18 + n_]).decode("utf-8", "replace")
                bgs = collections.Counter(int(x) for x in p[12:17])
                texts.append(dict(s=s, x=p[1], y=p[2], w=p[3], h=p[4], col=col, a=p[8], boxw=p[9], boxh=p[10],
                                  texth=p[11], bg=bgs.most_common(1)[0][0]))
            elif p[0] == 2:
                rects.append(dict(x=p[1], y=p[2], w=p[3], h=p[4], col=col, a=p[8], fill=p[9]))
            elif p[0] == 3:
                lines.append(dict(x1=p[1], y1=p[2], x2=p[3], y2=p[4], col=col, a=p[8], bg=int(p[9])))
        return Frame(texts, rects, focus, v, lines)

    def tab_to(self, fid, limit=80):
        for _ in range(limit):
            if int(self.var("focus_id")["focus_id"]) == fid:
                return True
            self.key("tab")
        return False

    def shot(self, path, w, h):
        raw = path + ".bgra"
        self.send("frame", "shot " + raw)
        try:
            import numpy as np
            from PIL import Image
            a = np.fromfile(raw, dtype=np.uint8).reshape(h, w, 4)
            Image.fromarray(a[:, :, [2, 1, 0]]).save(path)
            os.unlink(raw)
        except ImportError:
            print("      (numpy/PIL missing: left raw BGRA at %s)" % raw)

    def close(self):
        self.p.stdin.close()
        self.p.wait()


NAMES = {110: "Options", 113: "Dismiss", 114: "Undo", 101: "Build", 102: "Swell", 103: "Fade", 104: "Wander",
         105: "Panic", 1: "Pace", 2: "Change", 3: "Start", 4: "Peak", 5: "Feel", 6: "Variation",
         120: "Record", 121: "Clear", 122: "Drag Out", 123: "Insert", 124: "Place Take",
         130: "Keys From", 131: "Held Keys", 132: "Sustain Pedal", 133: "Dynamics"}
LAYERS = ["Bass", "Pad", "Pulse", "Arpeggio", "Sparkle"]
for _i, _n in enumerate(LAYERS):
    NAMES[200 + _i] = "%s on/off" % _n
    NAMES[210 + _i] = "%s Channel" % _n
    NAMES[220 + _i] = "%s Octave" % _n
    NAMES[230 + _i] = "%s Level" % _n


def name(fid):
    return NAMES.get(fid, "id %d" % fid)


ROWS = []
for _n in LAYERS:
    ROWS += ["%s on/off" % _n, "%s Channel" % _n, "%s Octave" % _n, "%s Level" % _n]
EVOLUTION = ["Build", "Swell", "Fade", "Wander", "Panic", "Pace", "Change", "Start", "Peak", "Feel", "Variation"]
MIDI = ["Keys From", "Held Keys", "Sustain Pedal", "Dynamics"]
ORDER_FRESH = ["Options"] + EVOLUTION + ROWS + ["Record", "Place Take"] + MIDI
ORDER_TAKE = ["Dismiss", "Options"] + EVOLUTION + ROWS + ["Record", "Clear", "Drag Out", "Insert", "Place Take"] + MIDI


# ---------------------------------------------------------------- static checks
G_NAMES = ["MAGIC", "HEART", "REQ", "KIND", "TRACK", "QN0", "COUNT", "TEMPO", "NUM", "DEN", "PLACE", "DONE",
           "RESULT", "LEN", "INST", "DONEINST", "MSGLEN", "MSG", "EVENTS"]


def static_checks(text):
    print("\n-- static: the source --")
    secs, _ = sections(text)
    cols = colours(text)
    off_ramp = {"C_ACCENT", "C_WARN", "C_WARN_TEXT"}
    bad = [k for k, v in cols.items() if k not in off_ramp and not ((v >> 16) < (v >> 8 & 255) < (v & 255))]
    check(not bad, "every grey is blue-shifted (R < G < B)", ", ".join(bad))
    for need, val in (("C_ACCENT", 0xFFF200), ("C_CTRL", 0xA9AFBA), ("C_GROUND", 0x23272E), ("C_INK", 0x14171C),
                      ("C_LABEL2", 0xB0B6C0), ("C_WARN_TEXT", 0xFF9E96), ("C_RING", 0xF2F4F7), ("C_TEXT", 0xDDE1E7)):
        check(cols.get(need) == val, "%s is the house #%06X" % (need, val), "found %s" % (hex(cols[need]) if need in cols else "nothing"))
    raw = [l for l in text.split("\n") if re.search(r"\bgfx_(r|g|b|a)\s*=", l) or "gfx_set(" in l]
    raw = [l for l in raw if not re.search(r"gfx_r = \(\(c|gfx_g = \(\(\(|gfx_b = \(c|gfx_a = (1|a);|gfx_r = rr|gfx_[rgba] = (rr|gg|bb|aa);", l)]
    check(not raw, "every colour goes through setx()/setxa()", "; ".join(x.strip() for x in raw[:3]))
    check("want_all_kb" not in text, "options:want_all_kb is not set (Space stays REAPER's)")
    check(re.search(r"^options:.*\bgmem=MidiEvolver\b", text, re.M) is not None, "the shared memory is named MidiEvolver")
    for nm, s in secs.items():
        clean = strip_code(s)
        check(clean.count("(") == clean.count(")"), "brackets balance in @%s" % nm,
              "%d ( against %d )" % (clean.count("("), clean.count(")")))
    gfx = secs["gfx"]
    sliders = sorted(int(n) for n in re.findall(r"^slider(\d+):", text, re.M))
    # @gfx writes sliders through set_slider(N, ...), or set_slider(base + L, ...) for a layer's row
    direct = {int(n) for n in re.findall(r"set_slider\((\d+),", gfx)}
    rows = {int(n) + L for n in re.findall(r"set_slider\((\d+) \+ L,", gfx) for L in range(5)}
    missing = [n for n in sliders if n not in direct | rows]
    check(not missing, "every slider has a control in the window", "missing: %s" % missing)
    disp = [n for n in sliders if not re.search(r"n == %d \? \( slider%d = v; sliderchange\(slider%d\); \)" % (n, n, n), gfx)]
    check(not disp, "set_slider names every slider it writes (so REAPER sees the change)", "%s" % disp)
    hidden = [n for n in re.findall(r"^slider\d+:[^>]*>(.)", text, re.M) if n != "-"]
    check(not hidden, "every slider is hidden from REAPER's slider panel (the window is the only surface)")
    for face in ('"Segoe UI"', '".AppleSystemUIFont"', '"Arial"', "gfx_getfont(#got)"):
        check(face in gfx, "the system font is asked for: %s" % face)
    # EEL2 names are case-insensitive: NL and nl are one variable
    code = strip_code("\n".join(v for k, v in secs.items() if k != "header"))
    seen = collections.defaultdict(set)
    for m in re.finditer(r"(?<![#\w.$'])[A-Za-z_]\w*", code):
        seen[m.group(0).lower()].add(m.group(0))
    twins = sorted("/".join(sorted(v)) for v in seen.values() if len(v) > 1)
    check(not twins, "no two names differ only in case (EEL2 would make them one)", ", ".join(twins))
    check(not re.search(r"(?<![\w.])\d+(?:\.\d*)?[eE][+-]?\d", strip_code(text)),
          "no number in 1e12 form (EEL2 cannot read it)")
    # memory regions, from the constants
    init = secs["init"]

    def const(n):
        m = re.search(r"\b%s\s*=\s*(\d+)\s*;" % n, init)
        return int(m.group(1)) if m else None
    regions = [
        ("held keys", const("held_base"), 128), ("keys down", const("down_base"), 128),
        ("velocities", const("hvel_base"), 128), ("chord", const("ch_base"), 128), ("pitch classes", const("ps_base"), 16),
        ("chord classes", const("cpc_base"), 12), ("colours", const("col_base"), 16),
        ("layers", const("L_on"), const("L_eprev") + 8 - const("L_on")),
        ("streams", const("rs_base"), 8), ("patterns", const("pat_base"), 5 * 32), ("pad", const("pad_base"), 44),
        ("pending", const("pend_base"), const("PN_MAX") * 6), ("sounding", const("an_base"), const("AN_MAX") * const("AN_W")),
        ("pitch slots", const("snd_base"), 16 * 128), ("output", const("oq_base"), const("OQ_MAX") * 4 + 4),
        ("input", const("ev_base"), const("EV_MAX") * 4), ("focus", const("focus_base"), const("FOCUS_MAX") * const("FOCUS_W")),
        ("live view", const("roll_base"), const("ROLL_MAX") * 5), ("take", const("rec_base"), const("REC_MAX") * 4),
    ]
    ok = all(r[1] is not None and r[2] for r in regions)
    clash = []
    if ok:
        rs = sorted(regions, key=lambda r: r[1])
        for a, b in zip(rs, rs[1:]):
            if a[1] + a[2] > b[1]:
                clash.append("%s overlaps %s" % (a[0], b[0]))
        top = rs[-1][1] + rs[-1][2]
        check(top < 3000000, "the plug-in's memory ends below the checker's own (3,000,000)", "ends at %d" % top)
    check(ok and not clash, "memory regions do not overlap", "; ".join(clash) or "a region is missing")
    # the gmem protocol agrees with the helper's
    lua = open(os.path.join(ROOT, "reascripts", "me_place.lua"), encoding="utf-8").read()
    gt = lua[lua.index("M.G = {"):lua.index("}", lua.index("M.G = {"))]
    lmap = {k: int(v) for k, v in re.findall(r"(\w+) = (\d+)", gt)}
    jmap = {k: int(v) for k, v in re.findall(r"\bG_(\w+) = (\d+);", init)}
    diff = [k for k in G_NAMES if lmap.get(k) is None or lmap.get(k) != jmap.get(k)]
    check(not diff, "the JSFX and the helper agree on every gmem slot", "differ: %s" % diff)
    lm = re.search(r"M.ME_MAGIC = (\d+)", lua)
    jm = re.search(r"ME_MAGIC = (\d+);", init)
    check(lm and jm and lm.group(1) == jm.group(1), "... and on the protocol's number")


# ---------------------------------------------------------------- window rules
DISABLED = re.compile(r"^(Clear|Drag Out…|Insert|Channel|Octave|Level|\d+|[+−]\d+|\d+ %|0)$")


def frame_rules(f, label, cols):
    S = f.v["ui_s"]
    gw, gh, top = f.v["gfx_w"], f.v["gfx_h"], f.v["top_h"]
    dim = cols["C_DIM"]
    low = []
    for t in f.texts:
        if t["y"] < top <= t["y"] + t["h"] or t["y"] + t["h"] > gh or not t["s"].strip():
            continue
        fg = mix(t["col"], t["bg"], t["a"])
        r = ratio(fg, t["bg"])
        if r < 7:
            if t["col"] == dim and DISABLED.match(t["s"]):
                continue
            low.append("'%s' %.2f:1 (#%06X on #%06X)" % (t["s"], r, fg, t["bg"]))
    check(not low, "%s: every line of text is at least 7:1 on what it sits on" % label, "; ".join(low[:4]))
    clipped = ["'%s' %.0f > %.0f" % (t["s"], t["w"], t["boxw"]) for t in f.texts
               if t["boxw"] >= 0 and t["w"] > t["boxw"] + 0.5]
    check(not clipped, "%s: no text is wider than its box (buttons never narrower than their labels)" % label,
          "; ".join(clipped[:4]))
    outside = ["'%s'" % t["s"] for t in f.texts if t["x"] < -0.5 or t["x"] + t["w"] > gw + 0.5]
    check(not outside, "%s: no text runs off the side of the window" % label, ", ".join(outside[:4]))
    small = ["'%s' %.1f" % (t["s"], t["texth"]) for t in f.texts if t["texth"] < 13 * S - 0.5]
    check(not small, "%s: no text is set under 13 points (x interface size)" % label, "; ".join(small[:4]))
    cut = ["'%s'" % t["s"] for t in f.texts if t["s"].endswith("…") and t["s"] != "Drag Out…"]
    check(not cut, "%s: no text is cut short with an ellipsis" % label, ", ".join(cut[:3]))
    view = [c for c in f.focus if c["id"] in (110, 113, 114) or (c["y"] >= top and c["y"] + c["h"] <= gh)]
    short = ["%s %.0f" % (name(c["id"]), c["h"]) for c in view if c["h"] < 28 * S - 0.5]
    check(not short, "%s: every control is at least 28 points tall" % label, ", ".join(short[:4]))
    wide = [name(c["id"]) for c in view if c["x"] < 0 or c["x"] + c["w"] > gw + 0.5]
    check(not wide, "%s: every control is inside the window" % label, ", ".join(wide))
    near = []
    for i, a in enumerate(view):
        for b in view[i + 1:]:
            hov = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            vov = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            if hov > 0 and vov > 0:
                near.append("%s overlaps %s" % (name(a["id"]), name(b["id"])))
            elif vov > 0 and -hov < 12 * S - 1:
                near.append("%s and %s %.0f apart" % (name(a["id"]), name(b["id"]), -hov))
            elif hov > 0 and -vov < 12 * S - 1:
                near.append("%s and %s %.0f apart" % (name(a["id"]), name(b["id"]), -vov))
    check(not near, "%s: controls are at least 12 points apart" % label, "; ".join(near[:4]))
    weak = []
    for c in view:
        if c["kind"] not in (2, 3):
            continue
        same = [r for r in f.rects if abs(r["x"] - c["x"]) < 0.5 and abs(r["y"] - c["y"]) < 0.5 and
                abs(r["w"] - c["w"]) < 0.5 and abs(r["h"] - c["h"]) < 0.5]
        fills = [r["col"] for r in same if r["fill"]]
        edges = [r["col"] for r in same if not r["fill"]]
        if not fills or not edges:
            weak.append("%s has no edge" % name(c["id"]))
            continue
        for under in (fills[-1], cols["C_POPUP"], cols["C_GROUND"]):
            if ratio(edges[-1], under) < 3:
                weak.append("%s #%06X on #%06X %.2f:1" % (name(c["id"]), edges[-1], under, ratio(edges[-1], under)))
    check(not weak, "%s: the edge of every field and setting is 3:1 on its fill and what is round it" % label,
          "; ".join(weak[:4]))
    # the two views: every mark 3:1 on their ground, but the beat and bar lines (texture)
    vx, vy, vw = f.v["vx"], f.v["vy"], f.v["vw"]
    y1 = f.v["ey"] + f.v["eh"]
    faint = set()
    for l in f.lines:
        if l["col"] in (cols["C_BEAT"], cols["C_SEP"]) or l["a"] < 0.2:
            continue
        if not (vx - 0.5 <= min(l["x1"], l["x2"]) <= vx + vw + 0.5 and vy - 0.5 <= min(l["y1"], l["y2"]) and max(l["y1"], l["y2"]) <= y1 + 0.5):
            continue
        fg = mix(l["col"], cols["C_ROLL"], l["a"])
        if ratio(fg, cols["C_ROLL"]) < 3:
            faint.add("#%06X %.2f:1" % (fg, ratio(fg, cols["C_ROLL"])))
    for r in f.rects:
        if not r["fill"] or r["col"] in (cols["C_ROLL"], cols["C_SEP"]) or not (vx < r["x"] < vx + vw and vy < r["y"] < y1):
            continue
        if ratio(mix(r["col"], cols["C_ROLL"], r["a"]), cols["C_ROLL"]) < 3:
            faint.add("note #%06X" % r["col"])
    check(not faint, "%s: every note and mark in the views is 3:1 on their ground" % label, "; ".join(sorted(faint)[:3]))


def ink_bar(f, cols, fid):
    c = next((c for c in f.focus if c["id"] == fid), None)
    if not c:
        return None
    S = f.v["ui_s"]
    return any(r["fill"] and r["col"] == cols["C_INK"] and r["h"] <= 3 * S + 0.5 and r["w"] > 8 * S and
               r["x"] >= c["x"] and r["x"] + r["w"] <= c["x"] + c["w"] and
               r["y"] >= c["y"] + c["h"] / 2 and r["y"] + r["h"] <= c["y"] + c["h"]
               for r in f.rects)


def ring_around(f, cols, c):
    S = f.v["ui_s"]
    rings = [r for r in f.rects if not r["fill"] and r["x"] <= c["x"] - 1 and r["y"] <= c["y"] - 1 and
             r["x"] + r["w"] >= c["x"] + c["w"] + 1 and r["y"] + r["h"] >= c["y"] + c["h"] + 1 and
             r["x"] >= c["x"] - 4 * S - 1 and r["w"] <= c["w"] + 8 * S + 2]
    return [r["col"] for r in rings]


def bar_text(f):
    """The message bar's words: everything drawn after its Options button."""
    last = max((i for i, t in enumerate(f.texts) if t["s"] == "Options"), default=-1)
    return " ".join(t["s"] for t in f.texts[last + 1:])


def gmem(u, n):
    u.send("setvar t_gm_n %d" % n, "frame", "setvar t_gm_n 0")
    return [float(x) for x in u.send("mem 6000000 %d" % n)[-1].split()[1:]]


def gwrite(u, i, v):
    u.send("setvar t_gw_i %d" % i, "setvar t_gw_v %g" % v, "frame")


def run_window(host, jsfx, cols, shots):
    def ui(w=860, h=780, scale=1):
        return UI(host, jsfx, w, h, scale)

    # ---- a fresh window: the rules, Tab order and the ring on every stop
    print("\n-- window: fresh, 100% --")
    u = ui()
    f = u.look()
    frame_rules(f, "fresh 100%", cols)
    if shots:
        u.shot(os.path.join(shots, "window-100.png"), 860, 780)
    order = [name(c["id"]) for c in f.focus]
    check(order == ORDER_FRESH, "Tab order is reading order, every control named (fresh)", "got %s" % order)
    check(bar_text(f).startswith("Hold a chord and let it grow"), "what to do is said at the top of the window",
          bar_text(f))
    check(ink_bar(f, cols, 101) is True, "the chosen shape carries an ink bar as well as the yellow")
    check(ink_bar(f, cols, 102) is False, "an unchosen shape carries no ink bar")
    last = max(c["y"] + c["h"] for c in f.focus)
    below = [t["s"] for t in f.texts if t["y"] > last]
    check(not below, "nothing is written below the last row of controls (no footer)", ", ".join(below))
    seen, missing, wrong = [], [], []
    for _ in range(len(f.focus)):
        u.key("tab")
        g = u.look()
        fid = int(g.v["focus_id"])
        seen.append(name(fid))
        c = next((c for c in g.focus if c["id"] == fid), None)
        found = ring_around(g, cols, c) if c else []
        if cols["C_RING"] not in found:
            missing.append(name(fid))
        if cols["C_ACCENT"] in found:
            wrong.append(name(fid))
    check(seen == ORDER_FRESH, "Tab visits every control once, in order", "visited %s" % seen)
    check(not missing, "a #F2F4F7 focus ring is drawn round every control Tab reaches", ", ".join(missing))
    check(not wrong, "the focus ring is never the accent yellow", ", ".join(wrong))
    u.key("tab")
    check(name(int(u.var("focus_id")["focus_id"])) == ORDER_FRESH[0], "Tab wraps from the last control to the first")
    u.key("tab", 1)
    check(name(int(u.var("focus_id")["focus_id"])) == ORDER_FRESH[-1], "Shift+Tab goes back")
    u.key("esc")
    check(int(u.var("focus_id")["focus_id"]) == 0, "Esc lets go of the focus")

    # ---- the keyboard alone
    print("\n-- window: the keyboard alone --")
    u.tab_to(102)
    u.key("space")
    check(int(u.var("slider1")["slider1"]) == 1, "Space presses a focused button (Swell chosen)")
    u.tab_to(1)
    base = u.var("slider2")["slider2"]
    u.key("up")
    a = u.var("slider2")["slider2"]
    u.key("down")
    b = u.var("slider2")["slider2"]
    check((a - base, b - a) == (1, -1), "the arrows nudge a field (Pace up a bar and back)", "%s" % [a - base, b - a])
    u.tab_to(2)
    c0 = u.var("slider3")["slider3"]
    u.key("up")
    u.key("up", 1)
    c2 = u.var("slider3")["slider3"]
    check(c2 - c0 == 6, "... in finer steps with Shift (Change +5, then +1)", "moved %s" % (c2 - c0))
    u.tab_to(202)
    u.key("ret")
    check(int(u.var("slider11")["slider11"]) == 0, "Return turns a focused layer off (Pulse)")
    f = u.look()
    check("Pulse Channel" not in [name(c["id"]) for c in f.focus], "a layer that's off leaves its fields out of the Tab order")
    u.key("ret")
    check(int(u.var("slider11")["slider11"]) == 1, "... and on again")
    u.tab_to(221)
    u.key("up")
    check(int(u.var("slider20")["slider20"]) == 1, "the arrows move a layer up an octave (Pad +1)")
    u.tab_to(131)
    u.key("right")
    check(int(u.var("slider30")["slider30"]) == 1, "the arrows step a setting (Held Keys to Played)")
    u.key("left")
    u.tab_to(6)
    u.key("ret")
    v = u.var("slider6", "slider7", "cur_seed")
    check(v["slider6"] == 1 and v["slider7"] == v["cur_seed"], "Variation locks to the last variation")
    f = u.look()
    check("Locked" in bar_text(f) and "%d" % v["cur_seed"] in bar_text(f), "... and says so, with its number", bar_text(f))
    u.key("ret")
    u.close()

    # ---- holding: the views, the layer rows and the recorder as music plays
    print("\n-- window: playing --")
    u = ui()
    u.send("note 60 100", "note 64 100", "note 67 100", "block 900")
    f = u.look()
    frame_rules(f, "holding a chord", cols)
    if shots:
        u.shot(os.path.join(shots, "window-playing.png"), 860, 780)
    vx, vy, vw, vh = (f.v[k] for k in ("vx", "vy", "vw", "vh"))
    notes = [r for r in f.rects if r["fill"] and vx < r["x"] < vx + vw and vy < r["y"] < vy + vh and
             r["col"] in (cols["C_ACCENT"], cols["C_CTRL"])]
    check(any(r["col"] == cols["C_ACCENT"] for r in notes) and any(r["col"] == cols["C_CTRL"] for r in notes),
          "the live view draws the notes: sounding ones yellow, finished ones grey", "%d notes" % len(notes))
    head = [t["s"] for t in f.texts if t["s"].startswith("Holding")]
    check(head and "C" in head[0] and "E" in head[0] and "G" in head[0] and "layers playing" in head[0],
          "it says which keys are held and how many layers play", "%s" % head)
    rows = [t["s"] for t in f.texts if "— playing" in t["s"]]
    check(len(rows) >= 2, "a layer that is playing says so in its row", "%s" % rows)
    dot = [r for r in f.rects if r["fill"] and r["col"] == cols["C_ACCENT"] and f.v["ey"] <= r["y"] <= f.v["ey"] + f.v["eh"]]
    check(f.v["holding"] == 1, "the window knows a chord is held")
    u.send("noteoff 60", "noteoff 64", "noteoff 67", "block 20")
    f = u.look()
    take = [t["s"] for t in f.texts if t["s"].startswith("The take:")]
    check(take and "bars" in take[0] and "notes" in take[0], "after the hold, the take is described (bars, notes)", "%s" % take)
    check([name(c["id"]) for c in f.focus][:2] == ["Options", "Build"] and "Drag Out" in [name(c["id"]) for c in f.focus],
          "with a take, Clear, Drag Out and Insert can be reached")
    helper = [t["s"] for t in f.texts if "need the helper" in t["s"] or "helper:" in t["s"]]
    check(bool(helper), "without the helper running, the window says how to start it", "%s" % helper[:1])

    # Drag Out: the take goes to shared memory; without the helper, the bar says what to do
    rn = int(u.var("rec_n")["rec_n"])
    u.tab_to(122)
    u.key("ret")
    f = u.look()
    check("needs the helper" in bar_text(f) and "Midi Evolver Helper" in bar_text(f),
          "Drag Out with no helper running says how to start it", bar_text(f))
    gm = gmem(u, 1000 + min(rn, 50) * 4)
    rec = [float(x) for x in u.send("mem 65536 %d" % (min(rn, 50) * 4))[-1].split()[1:]]
    check(gm[0] == 7301 and gm[2] >= 1 and gm[3] == 1 and int(gm[6]) == rn,
          "Drag Out leaves the request in shared memory: the protocol, a number, Drag Out, every message",
          "%s" % gm[:8])
    check(gm[1000:1000 + len(rec)] == rec, "... the messages exactly as the take holds them")
    check(gm[7] == 120 and gm[8] == 4 and gm[9] == 4, "... with the take's tempo and time signature")
    # the helper answers: heartbeat, then the answer for this request
    req, inst = gm[2], u.var("inst_id")["inst_id"]
    for k in range(3):
        gwrite(u, 1, 10 + k)
    f = u.look()
    check(f.v["helper_on"] == 1, "a moving heartbeat is read as the helper running")
    check(any(t["s"].startswith("The helper is running") for t in f.texts), "... and the window says so")
    msg = "Saved it."
    for i, ch in enumerate(msg):
        gwrite(u, 200 + i, ord(ch))
    gwrite(u, 199, len(msg))
    gwrite(u, 12, 1)
    gwrite(u, 15, inst)
    gwrite(u, 11, req)
    f = u.look()
    check(bar_text(f).startswith("Saved it."), "the helper's answer is shown at the top", bar_text(f))
    check(f.v["waiting"] == 0, "... and the window stops waiting")
    # Insert, then an answer for another plug-in is not ours
    u.tab_to(123)
    u.key("ret")
    req2 = gmem(u, 4)[2]
    check(req2 == req + 1 and gmem(u, 4)[3] == 2, "Insert asks with the next request number")
    for i, ch in enumerate("Other."):
        gwrite(u, 200 + i, ord(ch))
    gwrite(u, 199, 6)
    gwrite(u, 15, inst + 1)
    gwrite(u, 11, req2)
    f = u.look()
    check(not bar_text(f).startswith("Other."), "an answer meant for another Midi Evolver is not shown here")
    u.send("wait 3200")
    u.frame(2)
    f = u.look()
    check("didn’t answer" in bar_text(f), "a request nobody answers is said after a few seconds", bar_text(f))

    # Clear, and Undo brings it back
    u.tab_to(113)
    u.key("ret")
    u.tab_to(121)
    u.key("ret")
    f = u.look()
    check(int(u.var("rec_n")["rec_n"]) == 0 and "Cleared the take" in bar_text(f), "Clear empties the take and says so")
    check([name(c["id"]) for c in f.focus][0] == "Undo", "... with Undo beside the message, first in the Tab order")
    u.tab_to(114)
    u.key("ret")
    check(int(u.var("rec_n")["rec_n"]) == rn, "Undo brings the take back")

    # Record
    u.tab_to(120)
    u.key("ret")
    u.frame(2)
    f = u.look()
    check(f.v["rec_on"] == 1, "Record starts recording")
    check(ink_bar(f, cols, 120) is True and any(t["s"] == "Recording" for t in f.texts),
          "... its button reads Recording, in the accent with the ink bar")
    frame_rules(f, "recording", cols)
    u.tab_to(120)
    u.key("ret")
    u.frame(2)
    check(u.var("rec_on")["rec_on"] == 0, "clicking again stops it")
    # Panic from the window
    u.send("note 60 100", "note 64 100", "block 200")
    u.tab_to(105)
    u.key("ret")
    u.frame(2)
    check(u.var("holding")["holding"] == 0 and u.var("an_cnt")["an_cnt"] == 0, "Panic in the window stops everything")
    # every layer off: the warning, in words
    for L in range(5):
        u.send("slider %d 0" % (9 + L))
    u.send("setvar slider9 0")
    u.tab_to(113)
    u.key("ret")
    u.key("esc")
    f = u.look()
    w = [t for t in f.texts if t["y"] < f.v["top_h"] and t["s"].startswith("Every layer is off")]
    check(bool(w) and w[0]["col"] == cols["C_WARN_TEXT"], "with every layer off, the top says so in the warning colour (#FF9E96)")
    frame_rules(f, "every layer off", cols)
    u.close()

    # ---- messages stay
    print("\n-- window: messages --")
    u = ui()
    u.tab_to(105)
    u.key("ret")
    u.send("mouse -1 -1 0 0 0", "wait 1500")
    u.frame(60)
    f = u.look()
    check(bar_text(f).startswith("Panic"), "a message is still at the top 1.5 s and 60 frames later (no timer)")
    check(f.focus[0]["id"] == 113, "Dismiss comes first in the Tab order while a message shows")
    u.tab_to(113)
    u.key("ret")
    f = u.look()
    check(not bar_text(f).startswith("Panic"), "Dismiss clears the message")
    u.close()

    # ---- interface size
    print("\n-- window: interface size --")
    u = ui()
    small = u.look()
    u.tab_to(110)
    u.send("menu 3")
    u.key("ret")
    check(abs(u.var("ui_zoom")["ui_zoom"] - 1.5) < 1e-9, "Options → Interface Size 150% sets 150%")
    mt = u.send("menutext")[-1]
    check("Interface Size 100%" in mt and "Interface Size 200%" in mt and "!Interface Size 100%" in mt,
          "the menu offers 100% to 200% and ticks the current size", mt)
    u.send("reload")
    u.frame(2)
    check(abs(u.var("ui_zoom")["ui_zoom"] - 1.5) < 1e-9, "the interface size is remembered when the project reopens")
    for z, nm in ((1.25, "125%"), (1.5, "150%"), (2, "200%")):
        u.send("setvar ui_zoom %g" % z)
        f = u.look()
        frame_rules(f, "%s in 860 x 780" % nm, cols)
        if shots and z == 2:
            u.shot(os.path.join(shots, "window-200-small.png"), 860, 780)
    u.key("tab", 1)
    f = u.look()
    dyn = next(c for c in f.focus if c["id"] == 133)
    check(int(f.v["focus_id"]) == 133 and f.v["scroll"] > 0 and dyn["y"] >= f.v["top_h"] and dyn["y"] + dyn["h"] <= f.v["gfx_h"],
          "at 200% in a small window, Shift+Tab reaches Dynamics and scrolls it into view")
    u.key("tab")
    u.key("tab")
    f = u.look()
    bld = next(c for c in f.focus if c["id"] == 101)
    check(int(f.v["focus_id"]) == 101 and bld["y"] >= f.v["top_h"], "... and Tab on round to Build scrolls back up to it")
    u.close()
    for w, z, nm in ((560, 2, "200% in a 560-wide window"), (400, 1, "100% in a 400-wide window")):
        u = ui(w, 700)
        u.send("setvar ui_zoom %g" % z)
        f = u.look()
        frame_rules(f, nm, cols)
        if shots:
            u.shot(os.path.join(shots, "window-%d.png" % w), w, 700)
        u.close()
    # 200% in a window twice the size draws every control twice as big and as far
    u = ui(1720, 1560, 1)
    u.send("setvar ui_zoom 2")
    big = u.look()
    frame_rules(big, "200% in 1720 x 1560", cols)
    u.close()
    off = []
    sf = {c["id"]: c for c in small.focus}
    for c in big.focus:
        s = sf.get(c["id"])
        if not s or any(abs(c[k] - 2 * s[k]) > 4 + 0.03 * 2 * s[k] for k in "xywh"):
            off.append(name(c["id"]))
    check(not off and len(big.focus) == len(small.focus), "every control doubles exactly at 200%", ", ".join(off[:6]))
    print("\n-- window: a Retina screen --")
    u = ui(1720, 1560, 2)
    f = u.look()
    check(abs(f.v["ui_s"] - 2) < 1e-9, "on a Retina screen the window draws at twice the pixels", "ui_s %s" % f.v["ui_s"])
    frame_rules(f, "Retina 100%", cols)
    u.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsfx", default=os.path.join(ROOT, "Midi Evolver.jsfx"))
    ap.add_argument("--host", default=os.environ.get("MIDI_EVOLVER_HOST", os.path.join(HERE, "build", "host")))
    ap.add_argument("--static", action="store_true")
    ap.add_argument("--shots")
    a = ap.parse_args()
    text = open(a.jsfx, encoding="utf-8").read()
    cols = colours(text)
    static_checks(text)
    if not a.static:
        if not os.path.exists(a.host):
            print("no host at %s - run tools/build_host.sh (or --static)" % a.host)
            sys.exit(2)
        if a.shots:
            os.makedirs(a.shots, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "Midi Evolver-checked.jsfx")
            open(copy, "w", encoding="utf-8").write(instrument(text))
            run_window(a.host, copy, cols, a.shots)
    print("\n%d passed, %d failed" % (len(PASSES), len(FAILS)))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
