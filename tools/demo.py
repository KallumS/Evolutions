#!/usr/bin/env python3
"""
What Midi Evolver plays, printed bar by bar as note names, for reading the
music rather than the code. Read it before and after any musical change.

    python3 tools/demo.py                       # C E G held for 16 bars, Build, pace 8
    python3 tools/demo.py --keys 57 60 64 67 --bars 24 --shape 1 --pace 4
    python3 tools/demo.py --change 0 --seed 4182

Each bar shows each layer's notes in order, with where they fall in the bar
(beat.sixteenth) and their velocity. Needs tools/build/host (tools/build_host.sh).
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
LAYERS = ["Bass", "Pad", "Pulse", "Arpeggio", "Sparkle"]
SR, BS = 48000, 256


def name(p):
    return "%s%d" % (NAMES[p % 12], p // 12 - 1)


def run(keys, bars, shape, pace, change, start, peak, seed, tempo=120, num=4, den=4, extra=()):
    cmds = ["tempo %g %d %d" % (tempo, num, den), "slider 1 %d" % shape, "slider 2 %d" % pace,
            "slider 3 %d" % change, "slider 4 %d" % start, "slider 5 %d" % peak]
    for i in range(5):
        cmds.append("slider %d %d" % (14 + i, i + 1))      # each layer on its own channel, to tell them apart
    if seed:
        cmds += ["slider 6 1", "slider 7 %d" % seed]
    cmds += list(extra)
    cmds += ["note %d 100" % k for k in keys]
    beat_samples = SR * 60.0 / tempo
    blocks = int(bars * num * 4 / den * beat_samples / BS) + 2
    cmds += ["block %d" % blocks, "var cur_seed", "midi"]
    p = subprocess.run([os.path.join(HERE, "build", "host"), os.path.join(ROOT, "Midi Evolver.jsfx")],
                       input="\n".join(cmds) + "\n", capture_output=True, text=True)
    out = p.stdout.splitlines()
    seed_used = next((int(float(l.split("=")[1])) for l in out if l.startswith("VAR cur_seed")), 0)
    ev = [tuple(int(x) for x in l.split()[1:]) for l in out if l.startswith("MIDI ")]
    return ev, seed_used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", type=int, nargs="+", default=[60, 64, 67])
    ap.add_argument("--bars", type=int, default=16)
    ap.add_argument("--shape", type=int, default=0)
    ap.add_argument("--pace", type=int, default=8)
    ap.add_argument("--change", type=int, default=50)
    ap.add_argument("--start", type=int, default=20)
    ap.add_argument("--peak", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    ev, seed = run(a.keys, a.bars, a.shape, a.pace, a.change, a.start, a.peak, a.seed)
    beat = SR * 60.0 / 120
    if not ev:
        print("nothing played")
        return 1
    t0 = min(e[0] for e in ev if e[1] & 0xF0 == 0x90)
    print("Keys %s, shape %d, pace %d, change %d%%, variation %d" %
          (" ".join(name(k) for k in a.keys), a.shape, a.pace, a.change, seed))
    bars = {}
    for s, b1, b2, b3 in ev:
        if b1 & 0xF0 == 0x90 and b3 > 0:
            q = (s - t0) / beat
            bar, pos = int(q // 4), q % 4
            bars.setdefault(bar, {}).setdefault(b1 & 15, []).append((pos, b2, b3))
    for bar in sorted(bars):
        print("bar %d" % (bar + 1))
        for ch in sorted(bars[bar]):
            notes = bars[bar][ch]
            print("  %-9s %s" % (LAYERS[ch] if ch < 5 else "ch%d" % (ch + 1),
                                 " ".join("%s@%d.%d/%d" % (name(p), int(pos) + 1, int(round((pos % 1) * 4)) + 1, v)
                                          for pos, p, v in notes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
