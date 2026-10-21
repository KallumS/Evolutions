# 0007. The take: the last hold kept by itself, Record to gather, never lost to a touch

Taken 2026-10-21. Stands.

## Context

"There should be a recorder which allows you to drag the midi out." The
best moment is often the one nobody meant to record. But a long recording
must not be lost to a stray key.

## Decision

- **Without Record, the last hold is the take** - always there to drag out,
  replaced by the next hold.
- **Record** gathers every hold and the pauses between into one take, until
  **Recording** is clicked again.
- **A recorded take waits** for Drag Out, Insert, Clear or a new Record: a
  hold afterwards plays but is not kept, and the window says so.
- **Clear** has **Undo** beside its message.
- The take is every message the plug-in sent (notes on their channels, the
  dynamics CCs, your own keys if they were let through), timed on the
  take's own clock in beats - a loop going round lengthens the take rather
  than folding it. It is saved with the project.
- **Where Played** (when REAPER was playing as the take began) puts an
  inserted take back where it was played; else it goes to the edit cursor.

## Consequences

- The take is up to 100,000 messages - about forty minutes of all five layers at 120 bpm -
  and is part of the plug-in's state, so it is in REAPER's undo history too.
