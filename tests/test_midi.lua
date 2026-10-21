--[[ me_midi: reading a take and writing it as a MIDI file.

       lua5.4 tests/test_midi.lua     (or: python3 tools/run_lua.py tests/test_midi.lua)
]]
local C = dofile(((arg and arg[0] or ""):match("^(.*)[/\\]") or ".") .. "/check.lua")
local M = dofile(C.SCRIPTS .. "me_midi.lua")

-- variable length quantities, from the MIDI file specification's own table
for _, row in ipairs({ { 0, "\0" }, { 0x40, "\x40" }, { 0x7F, "\x7F" }, { 0x80, "\x81\x00" },
                       { 0x2000, "\xC0\x00" }, { 0x3FFF, "\xFF\x7F" }, { 0x4000, "\x81\x80\x00" },
                       { 0x0FFFFFFF, "\xFF\xFF\xFF\x7F" } }) do
  C.eq(M.varlen(row[1]), row[2], ("varlen %d"):format(row[1]))
end

-- a take as the JSFX leaves it: four numbers a message
local raw = {
  0.0, 0xB0, 1, 48,       -- dynamics before the notes
  0.0, 0x90, 36, 80,      -- bass on channel 1
  0.0, 0x91, 48, 50,      -- pad on channel 2
  0.5, 0x92, 64, 70,      -- pulse, channel 3
  0.75, 0x82, 64, 0,
  1.0, 0x92, 64, 72,      -- struck again
  1.25, 0x92, 64, 0,      -- a note-on of velocity 0 is a note-off
  4.0, 0x80, 36, 0,
  4.0, 0x81, 48, 0,
  2.0, 0xE0, 0, 64,       -- a pitch bend: kept as a message, not a note
  3.0, 0xF0, 0, 0,        -- not a channel message: dropped
}
local function nums(i) return raw[i + 1] end
local ev = M.decode(nums, #raw / 4)
C.eq(#ev, 10, "decode keeps the ten channel messages and drops the rest")
C.ok(ev[1].status == 0xB0 and ev[2].status == 0x90 and ev[3].status == 0x91,
     "at a shared moment messages stay in the order they were sent")
local sorted = true
for i = 2, #ev do if ev[i].beat < ev[i - 1].beat then sorted = false end end
C.ok(sorted, "decode puts the messages in time order")

local notes, ccs = M.notesOf(ev, 4)
C.eq(#notes, 4, "four notes")
C.eq(#ccs, 1, "one controller")
local byStart = {}
for _, n in ipairs(notes) do byStart[#byStart + 1] = ("%g:%d:%g:%d:%d"):format(n.start, n.pitch, n.len, n.vel, n.chan) end
table.sort(byStart)
local want = { "0:36:4:80:0", "0:48:4:50:1", "0.5:64:0.25:70:2", "1:64:0.25:72:2" }
table.sort(want)
C.eqList(byStart, want,
         "notes pair with their own offs, channel by channel (start:pitch:length:velocity:channel)")
local hanging = M.notesOf(M.decode(function(i) return ({ 1, 0x90, 60, 90 })[i + 1] end, 1), 8)
C.eq(hanging[1].len, 7, "a note with no end ends at the end of the take")

-- lengths in whole bars
C.eq(M.lengthInBars(0, 4, 4), 1, "an empty take is still a bar")
C.eq(M.lengthInBars(4, 4, 4), 1, "four beats are one bar of 4/4")
C.eq(M.lengthInBars(4.01, 4, 4), 2, "a little more is two")
local b, bar = M.lengthInBars(7, 3, 4)
C.ok(b == 3 and bar == 3, "seven beats of 3/4 are three bars")
C.eq(select(2, M.lengthInBars(6, 6, 8)), 3, "a bar of 6/8 is three quarter notes")

-- the file
local bytes = M.build(ev, 8, "Midi Evolver take", 96, 3, 4)
local f = M.parse(bytes)
C.ok(f ~= nil, "the file reads back")
C.ok(f.format == 0 and f.tracks == 1 and f.ppq == 960, "format 0, one track, 960 ticks a quarter")
local tempo, sig, name
for _, m in ipairs(f.metas) do
  if m.type == 0x51 then tempo = (m.data:byte(1) * 256 + m.data:byte(2)) * 256 + m.data:byte(3) end
  if m.type == 0x58 then sig = { m.data:byte(1), m.data:byte(2) } end
  if m.type == 0x03 then name = m.data end
end
C.eq(tempo, 625000, "the tempo is the take's (96 bpm = 625000 microseconds a quarter)")
C.ok(sig and sig[1] == 3 and sig[2] == 2, "the time signature is the take's (3/4)")
C.eq(name, "Midi Evolver take", "the track is named")
local last = f.metas[#f.metas]
C.ok(last.type == 0x2F and last.tick == 8 * 960, "the track ends at the length given (whole bars), not the last note")
C.eq(#f.events, 10, "every message is in the file")
-- at 0: the controller before the notes; at 4.0, both offs before anything new
C.ok(f.events[1].status == 0xB0, "a controller at the same moment comes before the notes it shapes")
local ok = true
for i = 2, #f.events do if f.events[i].tick < f.events[i - 1].tick then ok = false end end
C.ok(ok, "events are in time order")
local zeroOn = false
for _, e in ipairs(f.events) do if e.status >= 0x90 and e.status <= 0x9F and e.d2 == 0 then zeroOn = true end end
C.ok(not zeroOn, "a note-on of velocity 0 is written as a note-off")
-- a repeated pitch: its off comes before the next on at a shared tick
local rep = M.decode(function(i) return ({ 0, 0x90, 60, 90,  1, 0x90, 60, 91,  1, 0x80, 60, 0,  2, 0x80, 60, 0 })[i + 1] end, 4)
local rf = M.parse(M.build(rep, 4, "", 120, 4, 4))
C.ok(rf.events[2].status == 0x80 and rf.events[3].status == 0x90,
     "at a shared tick a note-off comes before a note-on, so a repeated note is not cut short")
local pb = nil
for _, e in ipairs(f.events) do if e.status == 0xE0 then pb = e end end
C.ok(pb and pb.d2 == 64 and pb.tick == 2 * 960, "a pitch bend is written where it was")

-- the file name
local nm = M.fileName(os.time({ year = 2026, month = 10, day = 21, hour = 14, min = 35, sec = 7 }))
C.eq(nm, "Midi Evolver 2026-10-21 14.35.07.mid", "a take's file is named for when it was saved")
C.ok(not nm:find("[/\\:*?\"<>|]"), "the name has nothing a file system refuses")

C.done()
