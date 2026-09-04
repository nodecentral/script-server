#!/usr/bin/env lua5.1
-- Name: confirm_gate.lua
-- Version: 1.0.0
-- Description: Reusable "type to confirm" safety-gate template for
--              destructive/impactful admin scripts. Demonstrates
--              Script-Server's interactive stdin support and a
--              preload_script info banner. Copy this pattern into any
--              script where you want an explicit confirmation step before
--              it does something impactful. Run standalone
--              (lua5.1 confirm_gate.lua) or from Script-Server.

local function out(s)
  io.write(s)
  io.flush()
end

out("This is a template for gating impactful actions behind a typed\n")
out("confirmation. Replace the action below with your real logic.\n\n")
out("Type CONFIRM to proceed: ")

local answer = io.read("*l")

if answer ~= "CONFIRM" then
  out("\nAborted - input did not match \"CONFIRM\".\n")
  os.exit(1)
end

out("\nConfirmed. Running the action...\n")
-- Replace this block with the real action.
out("(this is a template - nothing destructive happened)\n")
out("Done.\n")
