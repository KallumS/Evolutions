# 0001. A JSFX that plays, and a helper script that places

Taken 2026-10-21. Stands.

## Context

The user asked for "a JSFX that creates similar movements/motions to Olafur
Arnalds Cells by Spitfire Audio or Time Macro/Micro by Orchestral Tools
using only midi. When keys are pressed down on a keyboard the midi evolves
in real time for the duration that the keys are held down. There should be
a recorder which allows you to drag the midi out into Reaper."

The family has met this fork before. Good Idea, Midi Catalogue, Midi
Suggester and Midi Variator are ReaScripts, each with a decision "a
ReaScript, not a JSFX", because "a JSFX cannot write a file, reach the
REAPER API or start a drag" (Midi Catalogue 0001). Starting Blocks 1 was a
JSFX with a bridge script and a shared-memory protocol; version 2 dropped
the JSFX. AutoCC is the family's one JSFX, because it answers notes live.

## Decision

Two parts, each doing what only it can:

- **The JSFX plays.** Answering held keys in real time, sample-accurately,
  in time with REAPER's beat, is what a JSFX is for. A ReaScript can only
  stuff notes into the virtual keyboard on its next wake-up, some 30 ms
  late (Good Idea 0029's own measure), and can't see the keys you hold.
- **The JSFX records.** It keeps everything it sends as the take, in its
  own memory, saved with the project.
- **A helper ReaScript places.** `Midi Evolver Helper.lua` runs in the
  background (no window) and answers the JSFX through gmem
  `MidiEvolver`: **Drag Out** writes the take as a `.mid` and opens it in
  REAPER's **Media Explorer** with `OpenMediaExplorer(path, false)`, where
  it is selected and can be dragged onto any track; **Insert** adds it to
  the plug-in's own track. The answer comes back in words for the JSFX's
  message bar.

A drag can't start from a JSFX window, nor from a ReaScript (ReaImGui and
js_ReaScriptAPI have no drag to the arrange view); the Media Explorer is
REAPER's own drag source, so the drag is REAPER's.

## Consequences

- The helper has to be running; the window says so, in words, with how to
  start it, and the request isn't lost - click again once it runs. It can
  be added to the startup actions.
- The protocol is in two files; `tools/uicheck.py` holds them together.
- REAPER's own *Record: output (MIDI)* records the JSFX's output too; the
  README says so, for anyone who prefers it.
- The engine is EEL2, which only runs inside REAPER - so it is tested in
  ysfx, the same compiler (`tools/enginecheck.py`), as AutoCC's window is.

## Alternatives

- **A ReaScript only.** Rejected: late notes, and no way to hear the keys
  you hold while you hold them.
- **The JSFX writing the file.** It can't: `file_open` reads only;
  `export_buffer_to_project` writes audio, not MIDI.
- **A ReaImGui window for the helper** with its own Drag Out. Rejected for
  now: one window, the JSFX's, is simpler; nothing in it needs a second.
