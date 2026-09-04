#!/usr/bin/env lua5.1
-- Name: progress_demo.lua
-- Version: 1.0.0
-- Description: Live-updating progress bar demonstrating Script-Server's
--              streamed terminal output and carriage-return (\r) handling.
--              Run standalone (lua5.1 progress_demo.lua --steps 20) or from
--              Script-Server.

local function getenv_num(name, default)
  local v = os.getenv(name)
  if v == nil or v == "" then return default end
  return tonumber(v) or default
end

local steps = getenv_num("PARAM_STEPS", 20)
local delay_ms = getenv_num("PARAM_DELAY_MS", 150)

local i = 1
while i <= #arg do
  if arg[i] == "--steps" and arg[i + 1] then
    steps = tonumber(arg[i + 1]) or steps
    i = i + 2
  elseif arg[i] == "--delay-ms" and arg[i + 1] then
    delay_ms = tonumber(arg[i + 1]) or delay_ms
    i = i + 2
  else
    i = i + 1
  end
end

local width = 30

local function sleep(ms)
  os.execute("sleep " .. (ms / 1000))
end

io.write(string.format("Running %d steps...\n", steps))
io.flush()

for n = 0, steps do
  local filled = math.floor((n / steps) * width)
  local bar = "[" .. string.rep("=", filled) .. string.rep(" ", width - filled) .. "]"
  io.write(string.format("\r%s %d%%", bar, math.floor((n / steps) * 100)))
  io.flush()
  sleep(delay_ms)
end

io.write("\nDone.\n")
io.flush()
