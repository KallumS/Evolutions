# 0009. A note ended before it has sounded is not played

Taken 2026-10-31. Stands.

## Context

Middaw runs this JSFX in its own EEL2 runtimes, and running the engine
check there many times showed the "nothing hanging" checks fail about one
run in six with a note-off "with nothing sounding". Both of Middaw's
runtimes (JavaScript, and the JSFX compiled to C) did it identically, and a
locked variation reproduced it every time, so it was this file and not the
host.

The cause: a note struck in a block's last sample, and ended in the same
block (a chord change, a layer leaving), has its end pushed to its start
plus two samples by `an_end` - which is past the block. `to_off` clamps both
the note-on and the note-off to the block's last sample, and the output sort
puts a note-off first at a shared offset (as it should, so a repeated note
retriggers). So the note-off went out before its own note-on, and the note
sounded until the next chord ended it.

## Decision

When `an_end` would put a note's note-off on the very offset of a note-on
queued this block, it takes that note-on back out of the queue
(`q_unsend`) instead of sending the note-off. The note would have lasted
under two samples; not playing it is the whole of its sound.

The alternative - carrying the note-off into the next block - keeps a
note in the table past the moment the engine ended it, where a new strike of
the same pitch could find it, and its late note-off would cut the new one.

## Consequences

- `tools/enginecheck.py` runs sixty locked variations through a chord
  change and fails if any note is left hanging; it fails on the old file
  (variations 14, 17, 25, 35, 50, with the hold four or two bars long).
- The take never records the note either: it records what is sent.
