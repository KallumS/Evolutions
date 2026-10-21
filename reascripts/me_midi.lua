--[[ Midi Evolver - a take, read and written out as MIDI.

     Pure Lua: no reaper., no ImGui. The helper hands it the numbers the
     JSFX left in shared memory and gets back notes, controllers and the
     bytes of a standard MIDI file.

     A take is a list of MIDI messages exactly as the JSFX sent them, each
     with its time in quarter notes from the start of the hold:

       { beat = 0.5, status = 0x92, d1 = 64, d2 = 71 }

     The writer is Good Idea's (Midi Catalogue's, itself Starting Blocks'),
     changed to write the messages as they come - notes and controllers on
     their own channels - rather than notes alone. Format 0, 960 ticks to the
     quarter note, done with arithmetic rather than bit operators so it does
     not care which Lua a REAPER build carries.
]]

local M = {}

M.PPQ = 960

------------------------------------------------------------------------------
-- Reading the take
------------------------------------------------------------------------------

-- `nums` is a function (i) -> the i-th number of the events area, 0-based,
-- four to a message: beat, status, data 1, data 2.
function M.decode(nums, count)
  local ev = {}
  for i = 0, math.max(0, math.floor(count or 0)) - 1 do
    local s = math.floor(nums(i * 4 + 1) + 0.5)
    if s >= 0x80 and s <= 0xEF then
      ev[#ev + 1] = {
        beat = math.max(0, nums(i * 4)), status = s,
        d1 = math.max(0, math.min(127, math.floor(nums(i * 4 + 2) + 0.5))),
        d2 = math.max(0, math.min(127, math.floor(nums(i * 4 + 3) + 0.5))),
      }
    end
  end
  -- in time order, and at a shared moment in the order they were sent
  for i, e in ipairs(ev) do e.order = i end
  table.sort(ev, function(a, b)
    if a.beat ~= b.beat then return a.beat < b.beat end
    return a.order < b.order
  end)
  return ev
end

local function isOn(e) return e.status >= 0x90 and e.status <= 0x9F and e.d2 > 0 end
local function isOff(e)
  return (e.status >= 0x80 and e.status <= 0x8F) or (e.status >= 0x90 and e.status <= 0x9F and e.d2 == 0)
end

-- Notes as { start, len, pitch, vel, chan } and controllers as
-- { beat, chan, cc, value }. A note with no end (none should come) ends at
-- `endBeat`. A note struck again while it sounds ends where it is struck.
function M.notesOf(ev, endBeat)
  local notes, ccs, open = {}, {}, {}
  local function close(key, at)
    local n = open[key]
    if n then
      n.len = math.max(1 / 64, at - n.start)
      open[key] = nil
    end
  end
  for _, e in ipairs(ev) do
    local chan = e.status % 16
    local key = chan * 128 + e.d1
    if isOn(e) then
      close(key, e.beat)
      local n = { start = e.beat, len = 0, pitch = e.d1, vel = e.d2, chan = chan }
      notes[#notes + 1] = n
      open[key] = n
    elseif isOff(e) then
      close(key, e.beat)
    elseif e.status >= 0xB0 and e.status <= 0xBF then
      ccs[#ccs + 1] = { beat = e.beat, chan = chan, cc = e.d1, value = e.d2 }
    end
  end
  for key in pairs(open) do close(key, endBeat or 0) end
  return notes, ccs
end

-- How long the item is: the take rounded up to whole bars, at least one.
function M.lengthInBars(beats, num, den)
  local bar = (num or 4) * 4 / (den or 4)
  return math.max(1, math.ceil((beats or 0) / bar - 1e-6)), bar
end

------------------------------------------------------------------------------
-- Writing the file
------------------------------------------------------------------------------

local function be16(n) return string.char(math.floor(n / 256) % 256, n % 256) end
local function be32(n)
  return string.char(math.floor(n / 16777216) % 256, math.floor(n / 65536) % 256,
                     math.floor(n / 256) % 256, n % 256)
end

-- MIDI's variable length quantity: seven bits per byte, high bit set on every
-- byte but the last.
function M.varlen(n)
  n = math.max(0, math.floor(n))
  local bytes = { n % 128 }
  n = math.floor(n / 128)
  while n > 0 do
    table.insert(bytes, 1, (n % 128) + 128)
    n = math.floor(n / 128)
  end
  local out = {}
  for i = 1, #bytes do out[i] = string.char(bytes[i]) end
  return table.concat(out)
end

local function meta(typeByte, payload)
  return string.char(0xFF, typeByte) .. M.varlen(#payload) .. payload
end

local function tempoAndMetre(bpm, num, den)
  local usPerQN = math.floor(60000000 / math.max(bpm or 120, 1) + 0.5)
  local dd, d = 0, math.max(1, math.floor(den or 4))
  while d > 1 do d = d / 2; dd = dd + 1 end
  return M.varlen(0) .. meta(0x51, string.char(math.floor(usPerQN / 65536) % 256,
                                               math.floor(usPerQN / 256) % 256, usPerQN % 256)) ..
         M.varlen(0) .. meta(0x58, string.char(math.max(1, math.min(255, math.floor(num or 4))), dd, 24, 8))
end

-- The whole take as a format 0 file. `beats` is how long it is (the track
-- ends there, whole bars, so the item dropped into REAPER is bars long).
function M.build(ev, beats, name, bpm, num, den)
  local rows = {}
  for i, e in ipairs(ev) do
    -- at a shared tick: note-offs first, so a repeated note is not cut short
    -- by the end of the one before; controllers before the notes they shape
    local rank = isOff(e) and 0 or (isOn(e) and 2 or 1)
    rows[#rows + 1] = { tick = math.floor(e.beat * M.PPQ + 0.5), rank = rank, i = i, e = e }
  end
  table.sort(rows, function(a, b)
    if a.tick ~= b.tick then return a.tick < b.tick end
    if a.rank ~= b.rank then return a.rank < b.rank end
    return a.i < b.i
  end)
  local trk = { M.varlen(0) .. meta(0x03, name or ""), tempoAndMetre(bpm, num, den) }
  local last = 0
  for _, r in ipairs(rows) do
    local e = r.e
    local s, d2 = e.status, e.d2
    if isOff(e) then s, d2 = 0x80 + e.status % 16, 0 end
    trk[#trk + 1] = M.varlen(r.tick - last) .. string.char(s, e.d1 % 128, d2 % 128)
    last = r.tick
  end
  local endTick = math.max(math.floor((beats or 0) * M.PPQ + 0.5), last)
  trk[#trk + 1] = M.varlen(endTick - last) .. meta(0x2F, "")
  local body = table.concat(trk)
  return "MThd" .. be32(6) .. be16(0) .. be16(1) .. be16(M.PPQ) .. "MTrk" .. be32(#body) .. body
end

-- "Midi Evolver 2026-10-21 14.35.07.mid": sorts by time, safe on every system.
function M.fileName(t)
  return "Midi Evolver " .. os.date("%Y-%m-%d %H.%M.%S", t or os.time()) .. ".mid"
end

------------------------------------------------------------------------------
-- Reading a file back (for the tests, and to check a file before showing it)
------------------------------------------------------------------------------

local function u16(s, i) return s:byte(i) * 256 + s:byte(i + 1) end
local function u32(s, i) return ((s:byte(i) * 256 + s:byte(i + 1)) * 256 + s:byte(i + 2)) * 256 + s:byte(i + 3) end

-- Returns { format, tracks, ppq, events = { { tick, status, d1, d2 } },
-- metas = { { tick, type, data } } } or nil and why.
function M.parse(bytes)
  if type(bytes) ~= "string" or bytes:sub(1, 4) ~= "MThd" then return nil, "not a MIDI file" end
  local out = { format = u16(bytes, 9), tracks = u16(bytes, 11), ppq = u16(bytes, 13), events = {}, metas = {} }
  local i = 15
  while i <= #bytes do
    if bytes:sub(i, i + 3) ~= "MTrk" then return nil, "bad track at " .. i end
    local len = u32(bytes, i + 4)
    local j, stop, tick, running = i + 8, i + 8 + len, 0, nil
    while j < stop do
      local v = 0
      repeat
        local b = bytes:byte(j); j = j + 1
        v = v * 128 + b % 128
      until b < 128
      tick = tick + v
      local s = bytes:byte(j)
      if s == 0xFF then
        local ty = bytes:byte(j + 1); j = j + 2
        local n = 0
        repeat
          local b = bytes:byte(j); j = j + 1
          n = n * 128 + b % 128
        until b < 128
        out.metas[#out.metas + 1] = { tick = tick, type = ty, data = bytes:sub(j, j + n - 1) }
        j = j + n
      else
        if s >= 0x80 then running = s; j = j + 1 end
        out.events[#out.events + 1] = { tick = tick, status = running, d1 = bytes:byte(j), d2 = bytes:byte(j + 1) }
        j = j + 2
      end
    end
    i = stop
  end
  return out
end

return M
