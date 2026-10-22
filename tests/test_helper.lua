--[[ The helper against a mocked REAPER: reading a request from gmem, Drag
     Out (a file, shown in the Media Explorer), Insert (an item on the
     plug-in's track, one undo step), the answer, and the loop.

       lua5.4 tests/test_helper.lua
]]
local C = dofile(((arg and arg[0] or ""):match("^(.*)[/\\]") or ".") .. "/check.lua")
local R = dofile(C.HERE .. "/reaper_mock.lua")
R.install()
local Midi = dofile(C.SCRIPTS .. "me_midi.lua")
local Place = dofile(C.SCRIPTS .. "me_place.lua")

local TMP = os.getenv("TMPDIR") or "/tmp"
local ROOT = TMP .. "/midi-evolver-test-" .. tostring(os.time()) .. "-" .. tostring(math.random(1, 1e6))
os.execute('mkdir -p "' .. ROOT .. '"')

local EVOLVER = "JS: Midi Evolver - held chords grow into evolving motion"

-- a short take: a held C (bass), a pad note, two pulses, the dynamics
local TAKE = {
  { 0.0, 0xB0, 1, 50 }, { 0.0, 0x90, 36, 80 }, { 0.0, 0x91, 48, 52 },
  { 0.5, 0x92, 64, 70 }, { 0.75, 0x82, 64, 0 }, { 1.0, 0x92, 67, 72 }, { 1.4, 0x82, 67, 0 },
  { 5.0, 0x80, 36, 0 }, { 5.0, 0x81, 48, 0 },
}

local function fresh(project)
  R.reset()
  R.project = project or ""
  R.resource = ROOT .. "/resource"
  reaper.gmem_attach("MidiEvolver")
  R.gmem[0] = 7301
  Place.start()
end

local function read(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local s = f:read("a")
  f:close()
  return s
end

------------------------------------------------------------------------------
-- the loop
------------------------------------------------------------------------------
fresh()
C.eq(R.attached, "MidiEvolver", "the helper attaches to the JSFX's shared memory")
Place.tick(Midi)
local b1 = R.gmem[1]
Place.tick(Midi)
C.ok(b1 and R.gmem[1] ~= b1, "the heartbeat moves on every run of the loop (the JSFX watches it)")
C.eq(Place.tick(Midi), nil, "with nothing asked, nothing is done")
C.eq(R.gmem[11] or 0, 0, "... and nothing is answered")

-- a request left from before the helper started is not answered now
R.reset(); R.resource = ROOT .. "/resource"
reaper.gmem_attach("MidiEvolver")
R.request(5, 1, { events = TAKE, len = 5 })
Place.start()
C.eq(Place.tick(Midi), nil, "a request made before the helper started is left alone")
C.eq(#R.explorer, 0, "... nothing is saved for it")

-- the wrong protocol is left alone
fresh()
R.request(1, 1, { events = TAKE })
R.gmem[0] = 1234
C.eq(Place.tick(Midi), nil, "shared memory that isn't Midi Evolver's protocol is left alone")

------------------------------------------------------------------------------
-- Drag Out
------------------------------------------------------------------------------
local proj = ROOT .. "/My Song/My Song.rpp"
os.execute('mkdir -p "' .. ROOT .. '/My Song"')
fresh(proj)
R.request(1, 1, { events = TAKE, len = 5.0, tempo = 90, num = 4, den = 4, inst = 77 })
local code, text = Place.tick(Midi)
C.eq(code, 1, "Drag Out saves the take")
C.eq(#R.explorer, 1, "... and opens it in the Media Explorer")
local shown = R.explorer[1] and R.explorer[1].file or ""
C.ok(shown:find(ROOT .. "/My Song/Midi Evolver/", 1, true) == 1, "... in a Midi Evolver folder beside the project",
     shown)
C.ok(shown:match("Midi Evolver %d%d%d%d%-%d%d%-%d%d %d%d%.%d%d%.%d%d%.mid$") ~= nil, "... named for when it was saved")
C.eq(R.explorer[1] and R.explorer[1].play, false, "... selected, not played")
local f = Midi.parse(read(shown) or "")
C.ok(f ~= nil, "the file is a MIDI file")
if f then
  local ons = 0
  for _, e in ipairs(f.events) do if e.status >= 0x90 and e.status <= 0x9F and e.d2 > 0 then ons = ons + 1 end end
  C.eq(ons, 4, "... with every note of the take")
  local endTick = f.metas[#f.metas].tick
  C.eq(endTick, 8 * 960, "... two whole bars long (the take is 5 beats)")
  local tempo
  for _, m in ipairs(f.metas) do if m.type == 0x51 then tempo = (m.data:byte(1) * 256 + m.data:byte(2)) * 256 + m.data:byte(3) end end
  C.eq(tempo, math.floor(60000000 / 90 + 0.5), "... at the take's tempo")
end
local a = R.answer()
C.ok(a.done == 1 and a.result == 1 and a.inst == 77, "the answer goes back to the plug-in that asked")
C.ok(a.text:find("Media Explorer", 1, true) and a.text:find("drag it onto a track", 1, true),
     "... saying where it is and what to do", a.text)
C.ok(a.text:find("project’s Midi Evolver folder", 1, true), "... in the project's folder")

-- an unsaved project: REAPER's own folder, said so
fresh("")
R.request(2, 1, { events = TAKE, len = 5 })
Place.tick(Midi)
C.ok((R.explorer[1] and R.explorer[1].file or ""):find(ROOT .. "/resource/Midi Evolver/", 1, true) == 1,
     "with the project not saved, the file goes in REAPER's Midi Evolver folder")
C.ok(R.answer().text:find("save the project", 1, true), "... and the answer says so")

-- a folder that can't be written
fresh("")
R.resource = "/proc/no-such-place"   -- (mkdir says it cannot; that is the point)
R.request(3, 1, { events = TAKE, len = 5 })
local c3, t3 = Place.tick(Midi)
C.ok(c3 and c3 < 0 and t3:find("Couldn’t save", 1, true), "a folder that can't be written is said plainly", t3)

-- an empty take
fresh("")
R.request(4, 1, { events = {}, len = 0 })
local c4, t4 = Place.tick(Midi)
C.ok(c4 == -4 and t4:find("empty", 1, true), "an empty take is said, not saved")

------------------------------------------------------------------------------
-- Insert
------------------------------------------------------------------------------
local function tracks(n, evolverAt, recAt)
  for i = 1, n do
    local fx = { "VST: Some Synth" }
    if i == evolverAt then table.insert(fx, 1, EVOLVER) end
    R.track("Track " .. i, fx, i == recAt and { EVOLVER } or {})
  end
end

-- where played: on the plug-in's track (0-based index), at the beat the take began
fresh("")
tracks(3, 2)
R.request(10, 2, { events = TAKE, len = 5, track = 1, qn0 = 16, place = 0, inst = 9 })
local c, t = Place.tick(Midi)
C.eq(c, 2, "Insert puts the take in")
local tr = R.tracks[2]
C.eq(#tr.items, 1, "... on the plug-in's own track")
local item = tr.items[1]
C.ok(item and math.abs(item.pos * 2 - 16) < 1e-9, "... where it was played (beat 16, bar 5)")
C.ok(item and math.abs(item.len * 2 - 8) < 1e-9, "... two whole bars long")
C.eq(#item.take.notes, 4, "... with every note")
C.eq(#item.take.ccs, 1, "... and the controller")
local pulse
for _, n in ipairs(item.take.notes) do if n.pitch == 64 then pulse = n end end
C.ok(pulse and pulse.sp == 0.5 * 960 and pulse.ep == 0.75 * 960 and pulse.chan == 2 and pulse.vel == 70,
     "a note keeps its place, length, channel and velocity")
C.ok(item.take.ccs[1].chanmsg == 0xB0 and item.take.ccs[1].cc == 1 and item.take.ccs[1].value == 50,
     "the controller keeps its number and value")
C.ok(item.take.sorted, "the take is sorted once, after the notes go in")
local allNoSort = true
for _, n in ipairs(item.take.notes) do if not n.noSort then allNoSort = false end end
C.ok(allNoSort, "... each note inserted without sorting")
C.eq(item.take.name, "Midi Evolver take", "the item is named")
C.ok(#R.undoNames == 1 and R.undoNames[1] == "Midi Evolver: insert take" and R.undoDepth == 0,
     "it is one undo step")
C.ok(t:find("bar 5", 1, true) and t:find("Undo takes it out", 1, true), "the answer says where, and how to undo it", t)
C.eq(#R.tracks[1].items + #R.tracks[3].items, 0, "no other track gets anything")

-- at the edit cursor
fresh("")
tracks(2, 1)
R.cursor = 3.0          -- seconds: beat 6 at 120
R.request(11, 2, { events = TAKE, len = 5, track = 0, qn0 = 16, place = 1 })
Place.tick(Midi)
local it = R.tracks[1].items[1]
C.ok(it and math.abs(it.pos - 3.0) < 1e-9, "Place Take At Edit Cursor: the item starts at the edit cursor")
C.ok(R.answer().text:find("edit cursor", 1, true), "... and the answer says so")
-- stopped when it was played: the edit cursor as well
fresh("")
tracks(2, 1)
R.cursor = 1.0
R.request(12, 2, { events = TAKE, len = 5, track = 0, qn0 = -1, place = 0 })
Place.tick(Midi)
it = R.tracks[1].items[1]
C.ok(it and math.abs(it.pos - 1.0) < 1e-9, "a take played with REAPER stopped goes to the edit cursor")

-- finding the track
fresh("")
tracks(4, 3)
R.request(13, 2, { events = TAKE, len = 5, track = 3, qn0 = 0 })   -- counted from 1 by mistake
Place.tick(Midi)
C.eq(#R.tracks[3].items, 1, "a track number one too high (counted from 1) still finds the plug-in's track")
fresh("")
tracks(4, 4)
R.request(14, 2, { events = TAKE, len = 5, track = 0, qn0 = 0 })   -- wrong altogether
Place.tick(Midi)
C.eq(#R.tracks[4].items, 1, "a wrong track number: the one track with Midi Evolver on it")
fresh("")
tracks(3, 0, 2)
R.request(15, 2, { events = TAKE, len = 5, track = 1, qn0 = 0 })
Place.tick(Midi)
C.eq(#R.tracks[2].items, 1, "Midi Evolver in a track's input FX is found too")
fresh("")
tracks(3, 0)
R.selTracks = { R.tracks[3] }
R.request(16, 2, { events = TAKE, len = 5, track = -1, qn0 = 0 })   -- on the master: no track of its own
local _, t16 = Place.tick(Midi)
C.eq(#R.tracks[3].items, 1, "no Midi Evolver on any track: the selected track")
C.ok(t16:find("selected track", 1, true), "... and the answer says which", t16)
fresh("")
tracks(2, 0)
R.request(17, 2, { events = TAKE, len = 5, track = -1, qn0 = 0 })
local c17, t17 = Place.tick(Midi)
C.ok(c17 == -1 and t17:find("Select a track", 1, true), "no track at all: it says what to do")
C.eq(R.undoDepth, 0, "... and leaves no undo block open")
fresh("")
tracks(3, 1)
R.tracks[2].fx = { EVOLVER }      -- two tracks with it, and the number points at neither
R.request(18, 2, { events = TAKE, len = 5, track = 3, qn0 = 0 })
R.selTracks = { R.tracks[3] }
Place.tick(Midi)
C.eq(#R.tracks[3].items, 1, "two tracks with Midi Evolver and a number that fits neither: the selected track")
fresh("")
tracks(1, 1)
R.tracks[1].refuses = true
R.request(19, 2, { events = TAKE, len = 5, track = 0, qn0 = 0 })
local c19, t19 = Place.tick(Midi)
C.ok(c19 == -3 and R.undoDepth == 0, "an item REAPER refuses is said, and the undo block is closed")

-- an answer is one request's: the next needs a new number
fresh("")
tracks(1, 1)
R.request(20, 2, { events = TAKE, len = 5, track = 0, qn0 = 0 })
Place.tick(Midi)
Place.tick(Midi)
C.eq(#R.tracks[1].items, 1, "a request is answered once")
R.request(21, 2, { events = TAKE, len = 5, track = 0, qn0 = 8 })
Place.tick(Midi)
C.eq(#R.tracks[1].items, 2, "... and the next request is answered too")

------------------------------------------------------------------------------
-- the script itself
------------------------------------------------------------------------------
R.reset()
dofile(C.SCRIPTS .. "Midi Evolver Helper.lua")
C.eq(R.options[1], 5, "the script asks to stop when run again, and shows its action as on")
C.ok(type(R.deferred) == "function", "it keeps running in the background (defer)")
C.ok(type(R.atexit) == "function", "it has something to do when it stops")
R.atexit()
C.eq(R.options[#R.options], 8, "... which shows its action as off")

os.execute('rm -rf "' .. ROOT .. '"')
C.done()
