# 0008. The window follows Apple's guidelines, as the family's do

Taken 2026-10-21. Stands.

## Context

The user asked that the house style and guidelines be followed, and attached
Good Idea's review against Apple's HIG Foundations and the house colour
scheme. Every window in the family follows Apple's writing guidelines
(Noterator 0053) and HIG Foundations (Good Idea 0030 and 0031, AutoCC 0001).

## Decision

AutoCC's JSFX window, carried over whole - it is the family's answer to
these guidelines inside a JSFX - with its rules:

- every line of text 7:1; marks and edges 3:1; secondary text `#B0B6C0`,
  warnings in words `#FF9E96`, the house red only to mark;
- 13-point system text, controls 28 points tall and 12 apart, every size
  through `ui_s`; **Options → Interface Size** 100–200%, kept with the
  project; a Retina screen drawn at full resolution;
- the keyboard alone: Tab order is reading order, a near-white ring,
  Return/Space press, the arrows nudge, Esc lets go;
- a chosen button carries an ink bar as well as the yellow;
- messages at the top until dismissed, text that wraps rather than "…";
- words: title-style controls, verbs first, sentence-case hints that start
  with the control's name, messages that say what to do.

And the house scheme (`docs/COLOUR.md`), with the ground `#23272E` behind
everything, as the scheme says (AutoCC's window ground is darker).

## Consequences

`tools/uicheck.py` holds every rule by running the real window in ysfx; each
was broken on purpose and the check failed (`tools/bite.py`). What only
REAPER can show - its keys reaching the window, its fonts - is listed in
`docs/apple-hig-review.md`.
