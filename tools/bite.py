#!/usr/bin/env python3
"""
Proves a check bites: breaks Midi Evolver.jsfx on purpose in a temporary copy
(never the working tree), runs a checker on the copy and says whether it
failed. AutoCC's tools/bite.py, for both of Midi Evolver's checkers.

    python3 tools/bite.py engine "what is broken" "old text" "new text" [more old/new pairs]
    python3 tools/bite.py ui     "what is broken" "old text" "new text"

Prints BIT (a check failed, and which), MISSED (everything passed - the rule
is not really checked) or DID NOT APPLY (the old text is not in the file).
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
which, what, pairs = sys.argv[1], sys.argv[2], sys.argv[3:]
checker = {"engine": "enginecheck.py", "ui": "uicheck.py"}[which]
src = open(os.path.join(HERE, "..", "Midi Evolver.jsfx"), encoding="utf-8").read()
for old, new in zip(pairs[0::2], pairs[1::2]):
    if old not in src:
        print("DID NOT APPLY  %s  (%r not found)" % (what, old[:60]))
        sys.exit(2)
    src = src.replace(old, new)
with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, "Midi Evolver.jsfx")
    open(p, "w", encoding="utf-8").write(src)
    r = subprocess.run([sys.executable, os.path.join(HERE, checker), "--jsfx", p], capture_output=True, text=True)
fails = [l[6:].split("  -  ")[0] for l in r.stdout.splitlines() if l.startswith("FAIL")]
if r.returncode and fails:
    print("BIT     %s  (%d failed, first: %s)" % (what, len(fails), fails[0]))
elif r.returncode:
    print("BIT (crashed)  %s  %s" % (what, (r.stdout + r.stderr).strip().splitlines()[-1:]))
else:
    print("MISSED  %s" % what)
