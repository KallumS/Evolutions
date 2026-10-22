# Review against Apple's Human Interface Guidelines: Foundations

Midi Evolver's window checked against the 19 Foundations pages, the same
review the family's windows had (Good Idea's `docs/apple-hig-review.md`, the
copy the user attached on 2026-10-21, and AutoCC's, whose JSFX window this
one is built from). Decision [0008](decisions/0008-the-window-follows-apples-guidelines.md).

The window is drawn by a JSFX inside REAPER, so some guidance cannot apply:
a JSFX cannot reach VoiceOver, Dynamic Type or Increase Contrast, or read the
system's appearance. Where a guideline is not met for that reason, this says
so rather than counting it as met.

## How it is checked

`tools/uicheck.py` runs the real `@gfx` in ysfx (REAPER's EEL2 and drawing)
and measures, rather than guesses: the contrast of every string against the
pixels under it, the size of every control and the gaps between them, the
Tab order by name, the ring on every stop, keys, messages staying, the
interface size at 100–200% (and remembered), a window twice the size at 200%
(everything exactly doubled), narrow windows, a Retina screen, the live view's
notes and marks. Every rule was broken on purpose with `tools/bite.py` and
the check failed.

## The guidelines

| Item | Guideline (paraphrased) | Verdict | Here |
| --- | --- | --- | --- |
| ACC-01 | Familiar interactions, the same everywhere | met | AutoCC's controls, keys and words; the family's message bar |
| ACC-02 | Never one sense or channel only | met | A chosen button carries an ink bar; a ticked layer a tick; a playing layer the words "— playing" as well as its yellow bar |
| ACC-06 | Text can be enlarged to at least 200% | met | Options → Interface Size, 100–200% |
| ACC-07 | Icons and marks grow with the text | met | The tick, the ink bar, the curves' line weight through `ui_s` |
| ACC-08 | macOS type: 13 pt by default, never below 10 | met | 13 and 14 pt, nothing smaller (checked) |
| ACC-10 | Minimum contrast; 7:1 aimed for small text | met | Every line of text 7:1 (checked); dimmed words only on a control that is off (Apple exempts them) |
| ACC-11 | Contrast for marks too | met | Field edges, entry marks, the energy curve, notes: 3:1 or more on what they sit on (checked) |
| ACC-15 | Shape or text as well as colour | met | See ACC-02 |
| ACC-16 | Colour-blind pairings | met | Sounding and finished notes differ by lightness (yellow and grey), not hue alone |
| ACC-21 | Pair sound with sight | met | The live view and the layer meters show what plays |
| ACC-22 | Controls 28 × 28 pt by default | met | Every control 28 pt tall; the layer box a 28-pt target |
| ACC-23 | About 12 pt around controls | met | 12 pt (checked) |
| ACC-29/30 | Everything from the keyboard | met | Tab, Shift+Tab, Return/Space, the arrows (Shift: finer), Esc |
| ACC-31 | Don't override system shortcuts | met | No `want_all_kb`: Space stays REAPER's |
| ACC-32 | Esc lets go before anything else | met | Esc lets go of the focus |
| ACC-33 | Nothing times out | met | Messages stay until Dismiss (checked after 60 frames and 1.5 s) |
| ACC-35 | No sound without visible start and stop | met | Nothing plays unless you hold keys; letting go stops it; Panic stops everything |
| ACC-37 | Careful with motion | met | Only the live view moves, with the music; nothing blinks |
| ACC-43 | Confirm or undo hard-to-undo actions | met | Clear has Undo; Insert is one REAPER undo step; settings are REAPER undo points; a recorded take is never replaced by a stray hold |
| COL-01 | One colour, one meaning | met | Yellow only for what is on |
| COL-08 | Colour never alone | met | See ACC-02 |
| COL-12 | Each palette role for its job | met | The red marks, `#FF9E96` says; `#8A919C` only dimmed words |
| COL-14 | A primary action by fill, not by coloured text | met | The accent fills only chosen buttons |
| DRK-04 | Dark-only is fine for media apps | met | The house scheme; studio use |
| DRK-05 | Dim grounds, bright foregrounds | met | The ramp |
| DP-04 | Straight to the task | met | Hold a chord: nothing to set first |
| DP-06 | Mistakes cheap | met | See ACC-43 |
| DP-07 | Say what happens in the background | met | The window says whether the helper is running and what it did |
| DP-11 | Clear feedback | met | Hover, held, chosen, playing; each layer's state in words |
| LAY-01 | Most important at the top | met | The message, then what is playing, then the settings |
| LAY-03 | Group related items | met | Motion, Evolution, Layers, Recorder, MIDI |
| LAY-07/09 | Adapt to window sizes; test the extremes | met | 400 to 1720 wide, 100% and 200%, checked |
| LAY-08 | Wrap rather than crop | met | Rows wrap; a layer's fields go under its name; words wrap - no "…" (checked) |
| LAY-16 | Nothing critical at the bottom edge | met | Messages at the top; the window scrolls |
| TYP-01/07 | System font, 13 pt | met | Segoe UI, San Francisco or Arial, whichever the system gives (`gfx_getfont`) |
| WRI-01…09 | Voice, plain words, verbs first, title-style controls | met | "Drag Out…", "Place Take", hints starting with the control's name |
| WRI-14 | Empty states say what to do | met | "Hold some keys and the music they start appears here." |
| WRI-18 | No blame; say how to fix it | met | "Drag Out needs the helper. In REAPER's Actions list, run “Midi Evolver Helper”, then click Drag Out again." |
| WRI-22 | Toggle hints describe the on state | met | Each setting's hint names what each value does |

## Not met, because a JSFX can't

- **VoiceOver, Voice Control and Switch Control** cannot read a JSFX window.
- **Dynamic Type, Increase Contrast, Reduce Motion** cannot be read from a
  JSFX. Interface Size and the 7:1 colours stand in for the first two.
- **Right to left**: English only; time runs left to right, as in every DAW.

## Not relevant

Materials, app icons, SF Symbols, images, spatial and immersive design, games.

## Unverified in REAPER

- Whether REAPER hands Tab, Return, the arrows and Esc to the window in
  every set-up (AutoCC's open question too).
- Which face the system font resolves to on each system.
- How the live view keeps up on a track REAPER processes ahead of time.
