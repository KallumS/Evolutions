# The colour scheme

Every colour the window uses. It is the house scheme, the same as Good Idea,
AutoCC, Starting Blocks, Midi Suggester, Midi Variator, Midi Catalogue and
ScaleView: a dark cool-grey ground, a light grey for the controls raised off
it, and one yellow for whatever is switched on - and, in the live view, the
notes sounding now.

This file was copied from Good Idea's (which copied it from Midi Catalogue
and Starting Blocks) and is **not generated**: it is a reference kept by
hand. If you change a colour in `Midi Evolver.jsfx` (the `C_` constants at
the top of `@init`), change it here too.

## The four that carry it

| | value | what it is |
| --- | --- | --- |
| Accent | `#FFF200` | whatever is switched on |
| Controls | `#A9AFBA` | buttons, raised off the ground |
| Ground | `#23272E` | the window behind everything |
| Ink | `#14171C` | the text on any button |

The accent goes on one thing only: what is on. A chosen button (Build,
Recording), a ticked layer, the field being dragged, the bar beside a layer
that is playing, its meter, the notes sounding now in the live view and the
hold's place on the energy curve. Nothing decorative takes it.

## The live view

Midi Evolver's one addition, after Good Idea's roll (its decision 0009):
**a note sounding now is the accent, a note that has finished is the
controls' grey `#A9AFBA`**, on the roll's ground `#111419`. Beat lines are
`#1E2228` and bar lines `#3A404A` - texture, not marks. The energy curve is
the secondary text grey `#B0B6C0`; the layers' entry marks at its sides are
`#6D7581` (3:1); the hold's line is `#F2F4F7`.

## The grey ramp

| | used for |
| --- | --- |
| `#111419` | the live view's ground; plates under its words |
| `#14171C` | borders, and the text on every button |
| `#1A1D23` | fields and settings (sunken) |
| `#1B1F25` | a layer's row |
| `#1E2228` | beat lines |
| `#22262D` | row hover |
| `#23272E` | the ground; the message bar |
| `#2A2F37` | a playing layer's row; a button that is off |
| `#3A404A` | separators, panel edges, bar lines |
| `#6D7581` | the edge of a field or setting; marks (3:1) |
| `#8A919C` | dimmed words of a control that is off - never other words |
| `#8F96A2` | button held |
| `#A9AFBA` | buttons; finished notes |
| `#B0B6C0` | secondary text (7.35:1 on the ground) |
| `#C0C6CF` | button hover |
| `#DDE1E7` | body text |
| `#F2F4F7` | the focus ring; the hold's line |

## Off the ramp

`#D2483F` - red, to **mark** a warning, never for words (3.4:1). Words of a
warning are `#FF9E96` (7.55:1): "Every layer is off, so holding keys plays
nothing." The yellow and the two reds are the only saturated colours.

## Hover and held

| | rest | hover | held | how |
| --- | --- | --- | --- | --- |
| Controls | `#A9AFBA` | `#C0C6CF` | `#8F96A2` | set by hand |
| Accent | `#FFF200` | `#FFF42E` | `#D1C600` | computed by `shade()`, ±18% toward white and black |

## Two rules worth carrying

**Keep the greys blue.** R < G < B in every grey (`tools/uicheck.py` fails
otherwise). A neutral grey at the same lightness reads flat beside the
yellow.

**Light controls force dark text.** Every button, chosen or not, is lettered
in the ink `#14171C`; the body text colour would vanish on them.
