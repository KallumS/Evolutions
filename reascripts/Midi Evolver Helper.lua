-- @description Midi Evolver Helper
-- @author kallums
-- @version 1.0
-- @about
--   Runs in the background for the Midi Evolver JSFX: its Drag Out saves the
--   take as a MIDI file and shows it in the Media Explorer, to drag onto any
--   track, and its Insert puts the take on the plug-in's track. Run it once;
--   it stays running until REAPER closes, or until you run it again.

--[[ The JSFX plays and records; a JSFX cannot write a file, add an item or
     start a drag, so this does those for it (decision 0001). It has no
     window: everything is said in the JSFX's own message bar. Its action
     shows as on while it runs; running it again stops it.

     me_midi.lua (the take and the .mid) and me_place.lua (REAPER) sit
     beside this file. ]]

local here = debug.getinfo(1, "S").source:match("^@?(.*[/\\])") or ""
local Midi = dofile(here .. "me_midi.lua")
local Place = dofile(here .. "me_place.lua")

-- 1: running it again stops it; 4: its action shows as on.
if reaper.set_action_options then reaper.set_action_options(5) end

Place.start()

local function loop()
  Place.tick(Midi)
  reaper.defer(loop)
end

reaper.atexit(function()
  if reaper.set_action_options then reaper.set_action_options(8) end
end)

loop()
