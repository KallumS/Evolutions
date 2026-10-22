--[[ A REAPER that records instead of doing, for test_helper.

     Written from the API documentation's signatures (the REAPER 7.79 API
     functions page the user uploaded on 2026-10-21), not from what the
     scripts expect: a mock shaped by the code agrees with the code's bugs.
     Good Idea's mock, cut to what the helper calls, with gmem_attach,
     gmem_read, gmem_write, OpenMediaExplorer, TrackFX_GetFXName,
     TrackFX_GetRecCount, MIDI_InsertCC, GetActiveTake, set_action_options,
     defer and atexit added, each from its documented signature.

     Anything the scripts call that is not here raises, so a call to a
     function REAPER does not have fails in the test, not in REAPER.

     The project: tracks in a list (each with FX names), items on tracks,
     notes and CCs in takes in PPQ at 960 a quarter, one tempo (120 unless
     set) and one time signature.
]]

local P = {
  tracks = {}, selTracks = {}, gmem = {}, attached = nil,
  resource = "/tmp/midi-evolver-test-resource", project = "",
  tempo = 120, num = 4, den = 4, cursor = 0,
  undoDepth = 0, undoNames = {}, explorer = {}, options = {}, calls = {},
}

local PPQ = 960
local function qnPerSec() return P.tempo / 60 end
local function barQN() return P.num * 4 / P.den end

function P.track(name, fx, recFx)
  local t = { kind = "track", name = name or "", items = {}, fx = fx or {}, recFx = recFx or {}, alive = true }
  P.tracks[#P.tracks + 1] = t
  return t
end

local function takeStartQN(take) return take.item.pos * qnPerSec() end

local api = {
  -- Shared memory
  -- gmem_attach(sharedMemoryName); 6.20+ returns the previous name
  gmem_attach = function(name)
    if type(name) ~= "string" then error("gmem_attach(sharedMemoryName)") end
    local prev = P.attached
    P.attached = name
    return prev or ""
  end,
  -- gmem_read(index), index [0..1<<25)
  gmem_read = function(i)
    if P.attached ~= "MidiEvolver" then error("gmem_read before gmem_attach(\"MidiEvolver\")") end
    if math.type(i) ~= "integer" and i ~= math.floor(i) then error("gmem_read wants a whole index") end
    return P.gmem[math.floor(i)] or 0
  end,
  -- gmem_write(index, value)
  gmem_write = function(i, v)
    if P.attached ~= "MidiEvolver" then error("gmem_write before gmem_attach(\"MidiEvolver\")") end
    if type(v) ~= "number" then error("gmem_write(index, value)") end
    P.gmem[math.floor(i)] = v
  end,

  -- Tracks and FX
  CountTracks = function(_) return #P.tracks end,
  GetTrack = function(_, i) return P.tracks[i + 1] end,
  GetSelectedTrack = function(_, i) return P.selTracks[i + 1] end,
  TrackFX_GetCount = function(track) return #track.fx end,
  TrackFX_GetRecCount = function(track) return #track.recFx end,
  -- boolean retval, string buf = TrackFX_GetFXName(track, fx); fx + 0x1000000: record input FX
  TrackFX_GetFXName = function(track, fx)
    local list, i = track.fx, fx
    if fx >= 0x1000000 then list, i = track.recFx, fx - 0x1000000 end
    local n = list[i + 1]
    if not n then return false, "" end
    return true, n
  end,

  -- Time
  TimeMap2_timeToQN = function(_, t) return t * qnPerSec() end,
  TimeMap2_QNToTime = function(_, qn) return qn / qnPerSec() end,
  -- integer retval, optional number qnMeasureStart, optional number qnMeasureEnd
  TimeMap_QNToMeasures = function(_, qn)
    local b = barQN()
    local idx = math.floor(qn / b + 1e-9)
    return idx + 1, idx * b, (idx + 1) * b
  end,
  GetCursorPosition = function() return P.cursor end,

  -- Items and MIDI
  CreateNewMIDIItemInProj = function(track, t0, t1, qnIn)
    if qnIn then error("the scripts pass seconds") end
    if track.refuses then return nil end
    local take = { kind = "take", notes = {}, ccs = {}, name = "", sorted = true }
    local item = { kind = "item", track = track, pos = t0, len = t1 - t0, take = take }
    take.item = item
    track.items[#track.items + 1] = item
    return item
  end,
  GetActiveTake = function(item) return item.take end,
  MIDI_GetPPQPosFromProjQN = function(take, qn) return (qn - takeStartQN(take)) * PPQ end,
  -- boolean MIDI_InsertNote(take, selected, muted, startppqpos, endppqpos, chan, pitch, vel, optional noSortIn)
  MIDI_InsertNote = function(take, sel, muted, sp, ep, chan, pitch, vel, noSort)
    if type(sel) ~= "boolean" or type(muted) ~= "boolean" then error("MIDI_InsertNote(take, selected, muted, ...)") end
    take.notes[#take.notes + 1] = { sp = sp, ep = ep, pitch = pitch, vel = vel, chan = chan, noSort = noSort }
    take.sorted = false
    return true
  end,
  -- boolean MIDI_InsertCC(take, selected, muted, ppqpos, chanmsg, chan, msg2, msg3) - no noSort
  MIDI_InsertCC = function(take, sel, muted, ppq, chanmsg, chan, m2, m3, extra)
    if extra ~= nil then error("MIDI_InsertCC has no noSort argument") end
    take.ccs[#take.ccs + 1] = { ppq = ppq, chanmsg = chanmsg, chan = chan, cc = m2, value = m3 }
    take.sorted = false
    return true
  end,
  MIDI_Sort = function(take) take.sorted = true end,
  GetSetMediaItemTakeInfo_String = function(take, parm, value, set)
    if parm ~= "P_NAME" then error("mock has no take string " .. parm) end
    if set then take.name = value end
    return true, take.name
  end,
  UpdateArrange = function() end,

  -- Undo
  Undo_BeginBlock = function() P.undoDepth = P.undoDepth + 1 end,
  Undo_EndBlock = function(name, flags)
    P.undoDepth = P.undoDepth - 1
    if P.undoDepth < 0 then error("Undo_EndBlock without a begin") end
    if type(name) ~= "string" or name == "" then error("an undo block needs a name") end
    if math.type(flags) ~= "integer" then error("Undo_EndBlock(descchange, extraflags)") end
    P.undoNames[#P.undoNames + 1] = name
  end,

  -- Files and the Media Explorer
  GetResourcePath = function() return P.resource end,
  RecursiveCreateDirectory = function(path, _)
    os.execute('mkdir -p "' .. path .. '" 2>/dev/null')
    return 1
  end,
  -- ReaProject retval, optional string projfn = EnumProjects(integer idx)
  EnumProjects = function(idx)
    if idx ~= -1 then error("the scripts ask for the current project, -1") end
    return { kind = "project" }, P.project
  end,
  -- HWND OpenMediaExplorer(string mediafn, boolean play)
  OpenMediaExplorer = function(fn, play)
    if type(fn) ~= "string" or type(play) ~= "boolean" then error("OpenMediaExplorer(mediafn, play)") end
    P.explorer[#P.explorer + 1] = { file = fn, play = play }
    return "hwnd"
  end,

  -- The script's own life
  set_action_options = function(flag) P.options[#P.options + 1] = flag end,
  defer = function(f) P.deferred = f end,
  atexit = function(f) P.atexit = f end,
}

function P.install()
  reaper = setmetatable({}, {
    __index = function(_, k)
      local f = api[k]
      if f == nil then error("the script called reaper." .. tostring(k) .. ", which the mock does not have") end
      return f
    end,
    __newindex = function(_, k, v) api[k] = v end,
  })
  return reaper
end

function P.reset()
  P.tracks, P.selTracks, P.gmem, P.attached = {}, {}, {}, nil
  P.project, P.tempo, P.num, P.den, P.cursor = "", 120, 4, 4, 0
  P.undoDepth, P.undoNames, P.explorer, P.options, P.calls = 0, {}, {}, {}, {}
  P.deferred, P.atexit = nil, nil
end

-- What the JSFX's send_take() leaves in gmem: events { beat, status, d1, d2 }.
function P.request(id, kind, opts)
  local o = opts or {}
  local g = P.gmem
  g[0] = 7301
  for i, e in ipairs(o.events or {}) do
    local b = 1000 + (i - 1) * 4
    g[b], g[b + 1], g[b + 2], g[b + 3] = e[1], e[2], e[3], e[4]
  end
  g[3] = kind
  g[4] = o.track or 0
  g[5] = o.qn0 or -1
  g[6] = #(o.events or {})
  g[7] = o.tempo or 120
  g[8] = o.num or 4
  g[9] = o.den or 4
  g[10] = o.place or 0
  g[13] = o.len or 4
  g[14] = o.inst or 4242
  g[2] = id
end

function P.answer()
  local g = P.gmem
  local n = g[199] or 0
  local s = {}
  for i = 0, n - 1 do s[#s + 1] = string.char(g[200 + i]) end
  return { done = g[11], result = g[12], inst = g[15], text = table.concat(s) }
end

return P
