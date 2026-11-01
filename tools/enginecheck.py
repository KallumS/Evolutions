#!/usr/bin/env python3
"""
Checks Midi Evolver's engine - what it plays - by running the real JSFX in
ysfx (the EEL2 compiler REAPER uses) and reading the MIDI it sends.

    tools/build_host.sh                 # once: builds tools/build/host
    python3 tools/enginecheck.py        # every check
    python3 tools/enginecheck.py --jsfx copy.jsfx   # check another copy (tools/bite.py)

Every check prints PASS or FAIL; the script exits non-zero if any failed.
None of this has been run inside REAPER: ysfx is the same language and the
same MIDI calls, not REAPER itself.
"""
import argparse
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SR, BS = 48000, 256
FAILS, PASSES = [], []


def check(ok, name, detail=""):
    (PASSES if ok else FAILS).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (("  -  " + detail) if detail and not ok else ""))
    return ok


class Run:
    """One fresh plug-in, driven by commands; collects everything it sends."""

    def __init__(self, host, jsfx, tempo=120, num=4, den=4, sliders=None):
        self.p = subprocess.Popen([host, jsfx], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, bufsize=1)
        self.tempo, self.num, self.den = tempo, num, den
        self.ev = []           # (sample, b1, b2, b3)
        self.send("tempo %g %d %d" % (tempo, num, den))
        for n, v in (sliders or {}).items():
            self.send("slider %d %g" % (n, v))
        self.send("block 2")

    def send(self, *lines):
        for l in lines:
            self.p.stdin.write(l + "\n")
        self.p.stdin.write("midi\nsync\n")
        self.p.stdin.flush()
        out = []
        while True:
            l = self.p.stdout.readline()
            if not l:
                raise RuntimeError("host stopped: " + self.p.stderr.read())
            l = l.rstrip("\n")
            if l == "SYNC":
                break
            if l.startswith("MIDI "):
                self.ev.append(tuple(int(x) for x in l.split()[1:]))
            else:
                out.append(l)
        return out

    def var(self, *names):
        out = [l for l in self.send("var " + " ".join(names)) if l.startswith("VAR")]
        return {k: float(v) for k, v in (kv.split("=") for kv in out[-1].split()[1:])}

    def mem(self, addr, n):
        out = [l for l in self.send("mem %d %d" % (addr, n)) if l.startswith("MEM")]
        return [float(x) for x in out[-1].split()[1:]]

    def beats(self, b):
        """Run b beats of audio."""
        n = int(round(b * SR * 60.0 / self.tempo / BS))
        if n > 0:
            self.send("block %d" % n)

    def bars(self, n):
        self.beats(n * self.num * 4.0 / self.den)

    def hold(self, keys, vel=100, ch=1):
        self.send(*["note %d %d %d" % (k, vel, ch) for k in keys])

    def release(self, keys, ch=1):
        self.send(*["noteoff %d %d" % (k, ch) for k in keys])

    def close(self):
        self.p.stdin.close()
        self.p.wait()

    # ---- reading what was sent
    def ons(self, ch=None):
        return [e for e in self.ev if e[1] & 0xF0 == 0x90 and e[3] > 0 and (ch is None or e[1] & 15 == ch)]

    def beat_of(self, sample):
        return sample / (SR * 60.0 / self.tempo)


def hygiene(ev):
    """Note-ons and -offs pair up per channel and pitch: returns (problems, still sounding)."""
    sounding, bad = {}, []
    for s, b1, b2, b3 in ev:
        st, ch = b1 & 0xF0, b1 & 15
        if st == 0x90 and b3 > 0:
            if (ch, b2) in sounding:
                bad.append("note-on %d ch%d at %d while it sounds" % (b2, ch + 1, s))
            sounding[(ch, b2)] = s
        elif st == 0x80 or (st == 0x90 and b3 == 0):
            if (ch, b2) not in sounding:
                bad.append("note-off %d ch%d at %d with nothing sounding" % (b2, ch + 1, s))
            sounding.pop((ch, b2), None)
    return bad, sounding


LAYER_CH = {14: 1, 15: 2, 16: 3, 17: 4, 18: 5}   # each layer on its own channel, 1-5


def spread(extra=None):
    d = dict(LAYER_CH)
    d.update(extra or {})
    return d


def main_checks(host, jsfx):
    def run(**kw):
        return Run(host, jsfx, **kw)

    # ------------------------------------------------------------------ basics
    print("\n-- holding a chord --")
    r = run(sliders=spread())
    r.hold([60, 64, 67])
    r.bars(16)
    v = r.var("holding", "ch_n", "an_cnt")
    check(v["holding"] == 1 and v["ch_n"] == 3, "holding C E G is read as a three-note chord")
    layers = sorted({e[1] & 15 for e in r.ons()})
    check(layers == [0, 1, 2, 3, 4], "over 16 bars of Build every layer plays", "channels %s" % layers)
    pcs = {0, 4, 7}
    colour = {2, 9}          # D and A: a whole tone above C and G, a semitone from nothing held
    out = [e for e in r.ons() if e[2] % 12 not in pcs | colour]
    check(not out, "every note is a chord tone or a colour tone (D, A on C E G)",
          ", ".join("%d" % e[2] for e in out[:6]))
    check(not [e for e in r.ons() if e[2] % 12 in (5, 11, 1, 3, 6, 8, 10)],
          "no note a semitone from anything held (no F or B over C E G)")
    r.release([60, 64, 67])
    r.beats(1)
    bad, still = hygiene(r.ev)
    check(not bad, "every note-on is followed by its note-off, never doubled", "; ".join(bad[:3]))
    check(not still, "letting go stops everything", "%d still sounding" % len(still))
    check(r.var("an_cnt")["an_cnt"] == 0, "... and the plug-in agrees nothing is sounding")
    vels = [e[3] for e in r.ons()]
    check(min(vels) >= 1 and max(vels) <= 127, "every velocity is 1-127")
    r.close()

    # one bar after letting go there is silence, then a new hold starts again
    r = run()
    r.hold([62, 65, 69])
    r.bars(2)
    r.release([62, 65, 69])
    n = len(r.ons())
    r.bars(2)
    check(len(r.ons()) == n, "nothing plays after the keys are let go")
    r.hold([62, 65, 69])
    r.bars(1)
    check(len(r.ons()) > n, "a new hold starts again")
    r.close()

    # ------------------------------------------------------------------ order of layers
    print("\n-- the layers come in one after another --")
    r = run(sliders=spread({2: 4}))
    r.hold([60, 64, 67])
    r.bars(8)
    first = {}
    for s, b1, b2, b3 in r.ons():
        first.setdefault(b1 & 15, s)
    order = sorted(first, key=lambda c: first[c])
    check(order == [0, 1, 2, 3, 4] or order[:2] in ([0, 1], [1, 0]) and order[2:] == [2, 3, 4],
          "Build: bass and pad at once, then pulse, arpeggio, sparkle", "order %s" % order)
    b = {c: r.beat_of(first[c] - first[0]) for c in first}
    check(b.get(0, 9) < 0.2 and b.get(1, 9) < 0.2, "the bass and pad sound the moment the chord is held",
          "bass %.2f, pad %.2f beats" % (b.get(0, -1), b.get(1, -1)))
    check(b[2] < b[3] < b[4], "each later layer waits for more energy", "%s" % b)
    r.close()

    # a faster pace brings them in sooner
    def arp_first(pace):
        r = run(sliders=spread({2: pace}))
        r.hold([60, 64, 67])
        r.bars(20)
        ons = r.ons(3)
        t = r.beat_of(ons[0][0] - r.ons()[0][0]) if ons else 999
        r.close()
        return t
    fast, slow = arp_first(2), arp_first(16)
    check(fast < slow, "a faster pace brings the arpeggio in sooner (pace 2 against 16)",
          "%.1f against %.1f beats" % (fast, slow))

    # Fade: everything at once, then thinning out
    r = run(sliders=spread({1: 2, 2: 2, 4: 0}))
    r.hold([60, 64, 67])
    r.bars(1)
    early = {e[1] & 15 for e in r.ons()}
    n0 = len(r.ons())
    r.bars(4)
    r.ev = r.ev[0:0]
    r.bars(2)
    late = {e[1] & 15 for e in r.ons()}
    check(early >= {0, 1, 2, 3}, "Fade: the layers are there from the first bar", "%s" % sorted(early))
    check(len(late) < len(early), "Fade: fewer layers once it has thinned out", "%s then %s" % (sorted(early), sorted(late)))
    r.close()

    # Swell: grows and falls back
    r = run(sliders=spread({1: 1, 2: 2}))
    r.hold([60, 64, 67])
    counts = []
    for _ in range(4):
        r.ev = []
        r.bars(1)
        counts.append(len(r.ons()))
    check(counts[1] > counts[0] and counts[3] < max(counts), "Swell: busier as it grows, quieter as it falls",
          "notes per bar %s" % counts)
    r.close()

    # Peak below a layer's level keeps it out
    r = run(sliders=spread({5: 50}))
    r.hold([60, 64, 67])
    r.bars(16)
    check(not r.ons(4), "with Peak at 50% the sparkle (which comes in at 68%) never plays")
    r.close()

    # ------------------------------------------------------------------ variations
    print("\n-- a new variation each time, or the same one --")
    def take(sliders, keys=(60, 64, 67), bars=6):
        r = run(sliders=sliders)
        r.hold(list(keys))
        r.bars(bars)
        seq = [(round(r.beat_of(s), 3), b1, b2, b3) for s, b1, b2, b3 in r.ev if b1 & 0xF0 == 0x90]
        seed = r.var("cur_seed")["cur_seed"]
        r.close()
        t0 = seq[0][0] if seq else 0
        return [(round(a - t0, 3), b, c, d) for a, b, c, d in seq], seed
    a, sa = take(spread())
    b, sb = take(spread())
    check(sa != sb and a != b, "two holds of the same chord are different variations",
          "variations %d and %d" % (sa, sb))
    la, _ = take(spread({6: 1, 7: 4182}))
    lb, _ = take(spread({6: 1, 7: 4182}))
    check(la == lb and len(la) > 50, "locked to a variation, a hold plays the same again, note for note (feel too)")
    lc, _ = take(spread({6: 1, 7: 4183}))
    check(lc != la, "another locked number is another variation")

    # Change 0 with the energy steady: the arpeggio's figure goes round unchanged
    r = run(sliders=spread({3: 0, 4: 60, 5: 60, 8: 0, 6: 1, 7: 77}))
    r.hold([60, 64, 67])
    r.bars(12)
    arp = [e[2] for e in r.ons(3)]
    period = next((p for p in range(3, 13) if len(arp) > 3 * p and arp[p:p * 3] == arp[:p * 2]), None)
    check(period is not None, "with Change at 0% the arpeggio repeats its figure exactly", "figure %s" % arp[:16])
    check(period in (5, 6, 7) if period else False, "its figure is 5 to 7 notes, against a bar of 4 (it phases)",
          "period %s" % period)
    r.close()
    # with Change, it does not
    r = run(sliders=spread({3: 100, 4: 60, 5: 60, 8: 0, 6: 1, 7: 77}))
    r.hold([60, 64, 67])
    r.bars(12)
    arp2 = [e[2] for e in r.ons(3)]
    same = next((p for p in range(3, 13) if len(arp2) > 3 * p and arp2[p:] == arp2[:-p]), None)
    check(same is None, "with Change at 100% the figure keeps changing")
    r.close()

    # ------------------------------------------------------------------ colour and chords
    print("\n-- harmony --")
    rnd = random.Random(7)
    worst = []
    for trial in range(10):
        root = rnd.randint(48, 59)
        shape = rnd.choice([(0, 4, 7), (0, 3, 7), (0, 4, 7, 11), (0, 3, 7, 10), (0, 5, 7), (0, 7), (0,), (0, 4, 7, 9)])
        keys = [root + i for i in shape]
        r = run(sliders=spread({3: 100, 2: 2}))
        r.hold(keys)
        r.bars(8)
        held = {k % 12 for k in keys}
        if len(held) == 1:
            held.add((keys[0] + 7) % 12)
        for e in r.ons():
            pc = e[2] % 12
            if pc in held:
                continue
            if any((pc - h) % 12 in (1, 11) for h in held):
                worst.append("%s: %d" % (keys, e[2]))
            elif not any((pc - h) % 12 == 2 for h in held):
                worst.append("%s: %d not a whole tone above a chord tone" % (keys, e[2]))
        r.close()
    check(not worst, "over ten chords at 100% Change, a note outside the chord is always a whole tone above one, "
          "never a semitone from any", "; ".join(worst[:4]))

    # one key alone: its fifth is added, nothing else
    r = run(sliders=spread())
    r.hold([57])
    r.bars(8)
    check({e[2] % 12 for e in r.ons()} <= {9, 4, 11, 6}, "one key alone is a root with its fifth (and their colours)",
          "%s" % sorted({e[2] % 12 for e in r.ons()}))
    r.close()

    # a new chord while holding: every layer follows it
    r = run(sliders=spread({2: 2}))
    r.hold([60, 64, 67])
    r.bars(4)
    r.release([60, 64, 67])
    r.hold([57, 60, 64])          # A minor straight after, no gap in a block
    mark = len(r.ev)
    r.bars(4)
    after = [e for e in r.ev[mark:] if e[1] & 0xF0 == 0x90 and e[3] > 0]
    # what still sounds from C major is released; the new notes are A minor's (or its colours: B, D, F#)
    late_notes = [e for e in after if r.beat_of(e[0] - r.ev[mark][0]) > 0.2]
    wrong = [e[2] for e in late_notes if e[2] % 12 not in {9, 0, 4, 11, 2, 7}]
    check(late_notes and not wrong, "after a change of chord the notes are the new chord's", "%s" % wrong[:6])
    r.release([57, 60, 64])
    r.beats(1)
    bad, still = hygiene(r.ev)
    check(not bad and not still, "... and nothing is left hanging from either chord", "; ".join(bad[:3]))
    r.close()

    # The same, on sixty locked variations: a locked number plays the same
    # notes in any host, so a note left hanging is found every time rather
    # than one run in six. Struck in a block's last sample and ended at once,
    # a note used to get its note-off sorted before its note-on (0009).
    hung = []
    for var in range(1, 61):
        for held in (2, 4):
            r = run(sliders=spread({2: 2, 3: 100, 6: 1, 7: var}))
            r.hold([60, 64, 67]); r.bars(held); r.release([60, 64, 67])
            r.hold([57, 60, 64]); r.bars(2); r.release([57, 60, 64]); r.beats(2)
            bad, still = hygiene(r.ev)
            r.close()
            if bad or still:
                hung.append("variation %d after %d bars: %s" % (var, held, (bad or ["%d still sounding" % len(still)])[0]))
    check(not hung, "sixty locked variations, chord after chord: no note is left hanging", "; ".join(hung[:3]))

    # a rolled chord is one hold, not three
    r = run(sliders=spread())
    r.send("note 60 100", "block 1", "note 64 100", "block 1", "note 67 100")
    r.bars(1)
    pad = [e[2] for e in r.ons(1)]
    check(r.var("holds_n")["holds_n"] == 1 and len(pad) == 3,
          "a chord played a little spread is gathered into one hold", "pad %s" % pad)
    check({p % 12 for p in pad} == {0, 4, 7} and pad[0] == 48 and pad[1] - pad[0] >= 7,
          "the pad voices every chord tone, wide at the bottom (C3 G3 E4)", "pad %s" % pad)
    r.close()

    # on one channel, a quick arpeggio note on a pitch the pad holds strikes
    # it again but never ends it: every pad voice still sounds at the end
    r = run(sliders={9: 0, 11: 0, 13: 0, 3: 0, 4: 70, 5: 70, 8: 0, 6: 1, 7: 31})
    r.hold([60, 64, 67])
    r.bars(8)
    v = r.var("pad_n")
    voices = [int(x) for x in r.mem(1000, int(v["pad_n"]))]
    _, still = hygiene(r.ev)
    arp_hits = [e for e in r.ons(0) if e[2] in voices and r.beat_of(e[0]) > 1]
    lost = [p_ for p_ in voices if (0, p_) not in still]
    check(arp_hits and not lost, "on one channel, a short note on a pitch the pad holds never cuts the pad's note",
          "pad %s, lost %s, %d strikes on its pitches" % (voices, lost, len(arp_hits)))
    r.close()

    # too few voices for the chord: the fifth goes first
    r = run(sliders=spread({4: 0, 5: 0, 9: 0, 11: 0, 12: 0, 13: 0}))
    r.hold([50, 57, 60, 65])
    r.beats(1)
    pad = [e[2] for e in r.ons(1)]
    check(sorted(p_ % 12 for p_ in pad) == [0, 2, 5] and len(pad) == 3,
          "three pad voices for Dm7 leave out the fifth (D C F, a shell)", "pad %s" % pad)
    r.close()

    # ------------------------------------------------------------------ registers and layer settings
    print("\n-- the layers' settings --")
    r = run(sliders=spread({19: -1, 23: 1, 25: 0}))
    r.hold([60, 64, 67])
    r.bars(12)
    bass = [e[2] for e in r.ons(0)]
    check(bass and max(bass) <= 47 - 12 + 12 and min(bass) >= 19, "Bass at Octave −1 is an octave lower",
          "%s" % sorted(set(bass)))
    check(not r.ons(1), "Pad at Level 0 plays nothing")
    spk = [e[2] for e in r.ons(4)]
    check(spk and min(spk) >= 79, "Sparkle at Octave +1 is higher", "%s" % sorted(set(spk))[:5])
    r.close()
    r = run(sliders={9: 0, 10: 0, 11: 0, 12: 1, 13: 0, 17: 7})
    r.hold([60, 64, 67])
    r.bars(2)
    chs = {e[1] & 15 for e in r.ons()}
    check(chs == {6}, "with only the arpeggio on, it plays at once, on its own channel (7)", "%s" % chs)
    r.close()
    r = run(sliders={9: 0, 10: 0, 11: 0, 12: 0, 13: 0})
    r.hold([60, 64, 67])
    r.bars(2)
    check(not r.ons(), "with every layer off, nothing plays")
    r.close()

    # ------------------------------------------------------------------ MIDI in
    print("\n-- the keys --")
    r = run(sliders=spread({30: 0}))
    r.hold([60, 64, 67], ch=9)
    r.bars(1)
    check(r.ons() and not r.ons(8), "Held Keys Muted: your own keys are not sent")
    r.close()
    r = run(sliders={30: 1})
    r.hold([60, 64, 67])
    r.bars(1)
    r.release([60, 64, 67])
    r.beats(1)
    keys_out = [e[2] for e in r.ons() if e[2] in (64, 67) and e[3] == 100]
    bad, still = hygiene(r.ev)
    check(sorted(keys_out) == [64, 67], "Held Keys Played: your own keys are sent as well", "%s" % keys_out)
    check(not still, "... and released")
    r.close()
    r = run(sliders={29: 2})
    r.hold([60, 64, 67], ch=1)
    r.bars(1)
    gen = [e for e in r.ons() if e[3] != 100]
    thru = [e for e in r.ons() if e[3] == 100]
    check(not gen and len(thru) == 3, "Keys From channel 2: keys on channel 1 pass straight through, untouched")
    r.close()
    r = run(sliders={29: 2})
    r.hold([60, 64, 67], ch=2)
    r.bars(1)
    check(len(r.ons()) > 2, "... and keys on channel 2 start the music")
    r.close()
    r = run()
    r.send("cc 74 33", "block 1")
    check([e for e in r.ev if e[1] == 0xB0 and e[2] == 74 and e[3] == 33], "other MIDI passes through")
    r.close()

    # the sustain pedal
    r = run(sliders={31: 1})
    r.hold([60, 64, 67])
    r.beats(2)
    r.send("cc 64 127")
    r.release([60, 64, 67])
    n = len(r.ons())
    r.bars(2)
    check(len(r.ons()) > n and r.var("holding")["holding"] == 1, "Sustain Pedal Holds Keys: letting go with the pedal down keeps it evolving")
    check(not [e for e in r.ev if e[1] & 0xF0 == 0xB0 and e[2] == 64], "... and the pedal itself is not sent on")
    r.send("cc 64 0")
    r.beats(1)
    check(r.var("holding")["holding"] == 0, "... until the pedal comes up")
    bad, still = hygiene(r.ev)
    check(not still, "... when everything stops")
    r.close()
    r = run(sliders={31: 0})
    r.hold([60, 64, 67])
    r.send("cc 64 127")
    r.release([60, 64, 67])
    r.beats(1)
    check(r.var("holding")["holding"] == 0 and [e for e in r.ev if e[1] == 0xB0 and e[2] == 64],
          "Sustain Pedal Ignored: letting go stops it, and the pedal is passed on")
    r.close()

    # all notes off
    r = run()
    r.hold([60, 64, 67])
    r.beats(4)
    r.send("cc 123 0")
    r.beats(1)
    bad, still = hygiene(r.ev)
    check(not still and r.var("holding")["holding"] == 0, "All Notes Off stops everything")
    r.close()

    # dynamics CC
    r = run(sliders={32: 3, 2: 4})
    r.hold([60, 64, 67])
    r.bars(4)
    cc1 = [e[3] for e in r.ev if e[1] & 0xF0 == 0xB0 and e[2] == 1]
    cc11 = [e[3] for e in r.ev if e[1] & 0xF0 == 0xB0 and e[2] == 11]
    first_note = min(e[0] for e in r.ons())
    first_cc = min(e[0] for e in r.ev if e[1] & 0xF0 == 0xB0)
    check(cc1 and cc11 and cc1[-1] > cc1[0], "Dynamics CC1 and CC11: the energy is sent and rises with Build",
          "CC1 %s … %s" % (cc1[:3], cc1[-3:]))
    check(first_cc <= first_note, "... the first value before the first note (libraries read it at note-on)")
    check(all(a != b for a, b in zip(cc1, cc1[1:])), "... and only when it changes")
    r.close()

    # ------------------------------------------------------------------ REAPER's clock
    print("\n-- in time with REAPER --")
    # REAPER plays from beat 0; the chord comes in 0.37 beat later, off the beat.
    r = run(sliders=spread({4: 60, 5: 60, 8: 0}))
    r.send("transport 1 0")
    r.beats(0.37)
    r.hold([60, 64, 67])
    r.bars(4)
    spb = SR * 60.0 / r.tempo
    # transport started 2 blocks after the host began (the Run's own "block 2")
    t_start = 6 * BS
    grids = (0.25, 1 / 3.0, 0.5)
    off = []
    for s, b1, b2, b3 in r.ons(3) + r.ons(2):
        beat = (s - t_start) / spb
        if not any(abs(beat / g - round(beat / g)) * g < 0.012 for g in grids):
            off.append(round(beat, 3))
    check(not off, "while REAPER plays, the pulse and arpeggio fall on REAPER's beats, not on when the key went down",
          "off the grid at %s" % off[:5])
    r.close()

    # a hold with REAPER stopped counts its grid from the key; a hold after
    # Play counts it from REAPER's beat 0 again
    r = run(sliders=spread({4: 60, 5: 60, 8: 0}))
    r.beats(0.29)
    r.hold([60, 64, 67])
    r.bars(1)
    r.release([60, 64, 67])
    r.beats(1)
    r.ev = []
    r.send("transport 1 0")
    t_play = int(r.var("vt")["vt"] * SR * 60.0 / r.tempo)       # (vt counts beats from the host's start)
    r.beats(1.37)
    r.hold([60, 64, 67])
    r.bars(2)
    spb = SR * 60.0 / r.tempo
    off = []
    for s_, b1, b2, b3 in r.ons(3) + r.ons(2):
        beat = (s_ - t_play) / spb
        if not any(abs(beat / g - round(beat / g)) * g < 0.012 for g in grids):
            off.append(round(beat, 3))
    check(r.ons(3) and not off, "after a hold with REAPER stopped, a hold while it plays is on REAPER's beats again",
          "off the grid at %s" % off[:5])
    r.close()

    # a jump in REAPER (a loop going round) keeps everything in step and nothing stuck
    r = run(sliders=spread({8: 0}))
    r.send("transport 1 0")
    r.hold([60, 64, 67])
    r.bars(2)
    r.send("transport 1 0")      # back to the start, as a loop does
    r.bars(2)
    r.release([60, 64, 67])
    r.beats(1)
    bad, still = hygiene(r.ev)
    check(not bad and not still, "a loop going round mid-hold leaves nothing hanging", "; ".join(bad[:3]))
    r.close()

    # @init runs again when the transport starts: what sounds must go on, not hang
    r = run(sliders=spread())
    r.hold([60, 64, 67])
    r.bars(1)
    r.send("transport 1 0")
    r.bars(1)
    r.release([60, 64, 67])
    r.beats(1)
    bad, still = hygiene(r.ev)
    check(not still, "pressing Play while holding leaves no stuck notes")
    r.close()

    # 3/4 and another tempo
    r = Run(host, jsfx, tempo=97, num=3, den=4, sliders=spread({2: 2}))
    r.hold([62, 66, 69])
    r.bars(8)
    r.release([62, 66, 69])
    r.beats(1)
    bad, still = hygiene(r.ev)
    check(r.ons(3) and not bad and not still, "in 3/4 at 97 bpm it plays, and stops cleanly")
    r.close()

    # ------------------------------------------------------------------ long holds
    print("\n-- long holds --")
    for shape in range(4):
        r = run(sliders=spread({1: shape, 2: 2, 3: 100}))
        r.hold([55, 59, 62, 65])
        r.bars(48)
        v = r.var("an_cnt", "pn_n", "an_hi")
        n = len(r.ons())
        r.release([55, 59, 62, 65])
        r.beats(1)
        bad, still = hygiene(r.ev)
        check(not bad and not still and v["an_hi"] < 200 and n > (100 if shape == 2 else 300),
              "48 bars of %s at Change 100%%: steady, nothing hanging, nothing piling up" % ["Build", "Swell", "Fade", "Wander"][shape],
              "%d notes, %d slots used, %s" % (n, v["an_hi"], "; ".join(bad[:2])))
        pitches = [e[2] for e in r.ons()]
        check(min(pitches) >= 24 and max(pitches) <= 108, "... every note between C1 and C8",
              "%d to %d" % (min(pitches), max(pitches)))
        r.close()

    # ------------------------------------------------------------------ the take
    print("\n-- the recorder --")
    r = run(sliders=spread())
    r.hold([60, 64, 67])
    r.bars(3)
    r.release([60, 64, 67])
    r.beats(1)
    v = r.var("rec_n", "rec_notes", "take_ready", "take_live", "take_len", "take_kind")
    sent = [e for e in r.ev if e[1] & 0xF0 in (0x80, 0x90, 0xB0)]
    check(v["take_ready"] == 1 and v["take_live"] == 0 and v["take_kind"] == 1, "a hold is kept as the take once it ends")
    check(int(v["rec_n"]) == len(sent), "the take holds every message sent, no more", "%d against %d" % (v["rec_n"], len(sent)))
    check(int(v["rec_notes"]) == len(r.ons()), "the take counts its notes")
    rec = r.mem(65536, int(v["rec_n"]) * 4)
    spb = SR * 60.0 / r.tempo
    s0 = sent[0][0]
    worst = max(abs(rec[i * 4] - (sent[i][0] - s0) / spb - rec[0]) for i in range(len(sent)))
    check(worst < 0.002 and rec[0] < 0.1, "the take's times are the times they were sent, in beats from the hold",
          "worst %.4f beats" % worst)
    check(abs(v["take_len"] - (sent[-1][0] - s0) / spb) < 0.1, "the take is as long as the hold",
          "%.2f beats" % v["take_len"])
    r.hold([62, 65, 69])
    r.bars(1)
    r.release([62, 65, 69])
    r.beats(1)
    v2 = r.var("rec_notes", "take_len")
    check(v2["take_len"] < v["take_len"], "without Record, the next hold replaces the take")
    r.close()

    # Record gathers holds, with the pause between
    r = run(sliders=spread())
    r.send("setvar rec_req 1")
    r.beats(0.5)
    check(r.var("rec_on")["rec_on"] == 1, "Record turns recording on")
    r.hold([60, 64, 67])
    r.bars(1)
    r.release([60, 64, 67])
    r.bars(1)
    r.hold([62, 65, 69])
    r.bars(1)
    r.release([62, 65, 69])
    r.beats(1)
    v = r.var("take_live", "rec_notes", "rt")
    check(v["take_live"] == 1 and abs(v["rt"] - 13) < 1.5, "recording, two holds and the bar between are one take",
          "%.1f beats" % v["rt"])
    r.send("setvar rec_req 1")
    r.beats(0.5)
    v = r.var("rec_on", "take_ready", "take_kind", "take_len")
    check(v["rec_on"] == 0 and v["take_ready"] == 1 and v["take_kind"] == 2, "clicking again stops it and keeps the take")
    n_before = r.var("rec_n")["rec_n"]
    r.hold([60, 64, 67])
    r.bars(1)
    r.release([60, 64, 67])
    r.beats(1)
    check(r.var("rec_n")["rec_n"] == n_before, "a hold after a recorded take does not replace it")
    r.send("reload")
    r.beats(0.5)
    v = r.var("rec_n", "take_ready", "take_kind")
    check(v["rec_n"] == n_before and v["take_ready"] == 1, "the take is kept with the project (saved and reloaded)")
    r.close()

    # Panic
    r = run(sliders=spread())
    r.hold([60, 64, 67])
    r.bars(2)
    r.send("setvar panic_req 1")
    r.beats(0.5)
    bad, still = hygiene(r.ev)
    check(not still and r.var("holding")["holding"] == 0, "Panic stops everything")
    r.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsfx", default=os.path.join(ROOT, "Midi Evolver.jsfx"))
    ap.add_argument("--host", default=os.environ.get("MIDI_EVOLVER_HOST", os.path.join(HERE, "build", "host")))
    a = ap.parse_args()
    if not os.path.exists(a.host):
        print("no host at %s - run tools/build_host.sh" % a.host)
        sys.exit(2)
    main_checks(a.host, a.jsfx)
    print("\n%d passed, %d failed" % (len(PASSES), len(FAILS)))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
