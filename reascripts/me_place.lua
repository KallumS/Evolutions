--[[ Midi Evolver Helper - everything that touches REAPER.

     The JSFX can play, but it cannot write a file, add an item or start a
     drag (decision 0001). It leaves its take in shared memory, gmem
     "MidiEvolver", and this answers: Drag Out saves the take as a .mid and
     shows it in REAPER's Media Explorer, where it can be dragged onto any
     track; Insert puts it on the plug-in's own track as a new MIDI item.

     The protocol, shared with `Midi Evolver.jsfx` (its G_ constants; change
     both together - tools/uicheck.py checks they agree):

       0  magic, 7301 for this protocol
       1  the helper's heartbeat, moved on every run of the loop
       2  request number, written last by the JSFX
       3  what is asked: 1 Drag Out, 2 Insert
       4  the plug-in's track (get_host_placement: -1 the master)
       5  where the take began, in project quarter notes, or -1 (REAPER was
          stopped, or Place Take is At Edit Cursor)
       6  how many messages
       7  tempo, 8 and 9 the time signature, when the take began
       10 Place Take (0 Where Played, 1 At Edit Cursor)
       11 the request answered, written last by this side
       12 the answer: 1 saved and shown, 2 inserted, below 0 could not
       13 the take's length in quarter notes
       14 which plug-in asked, 15 which plug-in is answered
       199 the length of the answer's words, 200- the words, one character each
       1000- the messages: beat, status, data 1, data 2
]]

local M = {}

M.G = {
  MAGIC = 0, HEART = 1, REQ = 2, KIND = 3, TRACK = 4, QN0 = 5, COUNT = 6, TEMPO = 7,
  NUM = 8, DEN = 9, PLACE = 10, DONE = 11, RESULT = 12, LEN = 13, INST = 14,
  DONEINST = 15, MSGLEN = 199, MSG = 200, EVENTS = 1000,
}
M.ME_MAGIC = 7301
M.SPACE = "MidiEvolver"
M.FOLDER = "Midi Evolver"
M.DRAG, M.INSERT = 1, 2

local function G(i) return reaper.gmem_read(i) end

------------------------------------------------------------------------------
-- The request
------------------------------------------------------------------------------

function M.read(Midi)
  local g = M.G
  local r = {
    id = G(g.REQ), kind = math.floor(G(g.KIND) + 0.5), track = math.floor(G(g.TRACK) + 0.5),
    qn0 = G(g.QN0), count = math.floor(G(g.COUNT) + 0.5), tempo = G(g.TEMPO),
    num = math.floor(G(g.NUM) + 0.5), den = math.floor(G(g.DEN) + 0.5),
    place = math.floor(G(g.PLACE) + 0.5), len = G(g.LEN), inst = G(g.INST),
  }
  if r.tempo <= 0 then r.tempo = 120 end
  if r.num <= 0 then r.num = 4 end
  if r.den <= 0 then r.den = 4 end
  r.events = Midi.decode(function(i) return G(g.EVENTS + i) end, r.count)
  local last = 0
  for _, e in ipairs(r.events) do last = math.max(last, e.beat) end
  r.len = math.max(r.len or 0, last)
  return r
end

-- The words of an answer go back one character to a slot; the JSFX shows
-- them in its message bar.
function M.answer(r, code, text)
  local g = M.G
  local n = math.min(#text, 600)
  for i = 1, n do reaper.gmem_write(g.MSG + i - 1, text:byte(i)) end
  reaper.gmem_write(g.MSGLEN, n)
  reaper.gmem_write(g.RESULT, code)
  reaper.gmem_write(g.DONEINST, r.inst)
  reaper.gmem_write(g.DONE, r.id)
end

------------------------------------------------------------------------------
-- Which track
------------------------------------------------------------------------------

local function hasEvolver(track)
  for i = 0, reaper.TrackFX_GetCount(track) - 1 do
    local ok, name = reaper.TrackFX_GetFXName(track, i)
    if ok and name:find("Midi Evolver", 1, true) then return true end
  end
  for i = 0, reaper.TrackFX_GetRecCount(track) - 1 do
    local ok, name = reaper.TrackFX_GetFXName(track, 0x1000000 + i)
    if ok and name:find("Midi Evolver", 1, true) then return true end
  end
  return false
end

-- The track the plug-in is on. get_host_placement's track number is taken
-- to count from 0, as GetTrack does; that is unverified, so the track
-- there must have a Midi Evolver on it, the one before is tried too, then
-- the only track with one, then the selected track.
function M.findTrack(r)
  local n = reaper.CountTracks(0)
  for _, i in ipairs({ r.track, r.track - 1 }) do
    if i >= 0 and i < n then
      local t = reaper.GetTrack(0, i)
      if t and hasEvolver(t) then return t, "its own" end
    end
  end
  local found
  for i = 0, n - 1 do
    local t = reaper.GetTrack(0, i)
    if hasEvolver(t) then
      if found then found = false; break end
      found = t
    end
  end
  if found then return found, "its own" end
  local sel = reaper.GetSelectedTrack(0, 0)
  if sel then return sel, "the selected" end
  return nil
end

------------------------------------------------------------------------------
-- Drag Out: a file, shown in the Media Explorer
------------------------------------------------------------------------------

-- A "Midi Evolver" folder beside the saved project, else in REAPER's own
-- folder (Good Idea's choice for its .mid files, decision 0029 there).
function M.folder()
  local _, projfn = reaper.EnumProjects(-1)
  local dir = projfn and projfn:match("^(.*)[/\\][^/\\]*$")
  local sep = package.config:sub(1, 1) == "\\" and "\\" or "/"
  if dir and dir ~= "" then return dir .. sep .. M.FOLDER, true end
  return reaper.GetResourcePath() .. sep .. M.FOLDER, false
end

function M.dragOut(r, Midi, now)
  local dir, inProject = M.folder()
  reaper.RecursiveCreateDirectory(dir, 0)
  local sep = dir:find("\\", 1, true) and "\\" or "/"
  local name = Midi.fileName(now)
  local path = dir .. sep .. name
  local bars, bar = Midi.lengthInBars(r.len, r.num, r.den)
  local bytes = Midi.build(r.events, bars * bar, "Midi Evolver take", r.tempo, r.num, r.den)
  local f = io.open(path, "wb")
  if not f then
    return -2, "Couldn’t save the take in " .. dir .. ". Check that the folder can be written to, then try again."
  end
  f:write(bytes)
  f:close()
  reaper.OpenMediaExplorer(path, false)
  return 1, "Saved “" .. name .. "” and showed it in the Media Explorer — drag it onto a track. It’s in " ..
            (inProject and "the project’s Midi Evolver folder." or "REAPER’s Midi Evolver folder (save the project to keep takes beside it).")
end

------------------------------------------------------------------------------
-- Insert: a new item on the plug-in's track
------------------------------------------------------------------------------

function M.insert(r, Midi)
  local track, which = M.findTrack(r)
  if not track then
    return -1, "Couldn’t find a track for the take. Select a track, then click Insert again."
  end
  local cursorQN = reaper.TimeMap2_timeToQN(0, reaper.GetCursorPosition())
  local where = (r.place == 0 and r.qn0 >= 0) and "played" or "cursor"
  local startQN = where == "played" and r.qn0 or cursorQN
  local bars, bar = Midi.lengthInBars(r.len, r.num, r.den)
  local endQN = startQN + bars * bar
  reaper.Undo_BeginBlock()
  local item = reaper.CreateNewMIDIItemInProj(track, reaper.TimeMap2_QNToTime(0, startQN),
                                              reaper.TimeMap2_QNToTime(0, endQN))
  if not item then
    reaper.Undo_EndBlock("Midi Evolver: insert take", -1)
    return -3, "REAPER couldn’t make an item on that track. Try another track."
  end
  local take = reaper.GetActiveTake(item)
  local notes, ccs = Midi.notesOf(r.events, r.len)
  for _, n in ipairs(notes) do
    local a = reaper.MIDI_GetPPQPosFromProjQN(take, startQN + n.start)
    local b = reaper.MIDI_GetPPQPosFromProjQN(take, startQN + n.start + n.len)
    reaper.MIDI_InsertNote(take, false, false, a, math.max(a + 1, b), n.chan, n.pitch, n.vel, true)
  end
  for _, c in ipairs(ccs) do
    reaper.MIDI_InsertCC(take, false, false, reaper.MIDI_GetPPQPosFromProjQN(take, startQN + c.beat),
                         0xB0, c.chan, c.cc, c.value)
  end
  reaper.MIDI_Sort(take)
  reaper.GetSetMediaItemTakeInfo_String(take, "P_NAME", "Midi Evolver take", true)
  reaper.Undo_EndBlock("Midi Evolver: insert take", -1)
  reaper.UpdateArrange()
  local barNo = reaper.TimeMap_QNToMeasures(0, startQN + 1e-6)
  local onWhat = which == "its own" and "this track" or "the selected track"
  if where == "played" then
    return 2, ("Inserted the take on %s, at bar %d, where it was played. Undo takes it out."):format(onWhat, barNo)
  end
  return 2, ("Inserted the take on %s at the edit cursor. Undo takes it out."):format(onWhat)
end

------------------------------------------------------------------------------
-- The loop
------------------------------------------------------------------------------

M.state = { beat = 0, handled = nil }

-- Requests made before the helper started are old: their windows have told
-- the musician to try again, so they are not answered now.
function M.start()
  reaper.gmem_attach(M.SPACE)
  M.state.handled = reaper.gmem_read(M.G.REQ)
  M.state.beat = 0
end

function M.tick(Midi, now)
  local st = M.state
  st.beat = (st.beat % 1000000) + 1
  reaper.gmem_write(M.G.HEART, st.beat)
  local id = reaper.gmem_read(M.G.REQ)
  if id == st.handled or reaper.gmem_read(M.G.MAGIC) ~= M.ME_MAGIC then return nil end
  st.handled = id
  local r = M.read(Midi)
  local code, text
  if r.count <= 0 or #r.events == 0 then
    code, text = -4, "The take is empty. Hold some keys, then try again."
  elseif r.kind == M.DRAG then
    code, text = M.dragOut(r, Midi, now)
  elseif r.kind == M.INSERT then
    code, text = M.insert(r, Midi)
  else
    code, text = -5, "The helper didn’t understand that request. Update Midi Evolver and its helper together."
  end
  M.answer(r, code, text)
  return code, text
end

return M
