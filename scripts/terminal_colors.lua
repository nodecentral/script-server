#!/usr/bin/env lua5.1
-- Name: terminal_colors.lua
-- Version: 1.0.0
-- Description: Demonstrates ANSI colour/style codes as rendered by
--              Script-Server's "terminal" output format. Run standalone
--              (lua5.1 terminal_colors.lua) or from Script-Server.

local ESC = string.char(27)
local RESET = ESC .. "[0m"

local function out(s)
  io.write(s)
  io.flush()
end

local colors = {
  {"30", "Black"}, {"31", "Red"}, {"32", "Green"}, {"33", "Yellow"},
  {"34", "Blue"}, {"35", "Magenta"}, {"36", "Cyan"}, {"37", "White"},
}

out("Standard colours:\n")
for _, c in ipairs(colors) do
  out(ESC .. "[" .. c[1] .. "m" .. c[2] .. RESET .. "  ")
end
out("\n\n")

out("Bright colours:\n")
for _, c in ipairs(colors) do
  local bright = tostring(tonumber(c[1]) + 60)
  out(ESC .. "[" .. bright .. "m" .. c[2] .. RESET .. "  ")
end
out("\n\n")

out("Styles:\n")
out(ESC .. "[1mBold" .. RESET .. "  ")
out(ESC .. "[4mUnderline" .. RESET .. "  ")
out(ESC .. "[7mInverse" .. RESET .. "\n")
