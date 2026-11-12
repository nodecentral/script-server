-- ============================================================
-- shared/ensure_binary.lua
-- ============================================================
-- Description : Self-installs a missing system binary (ffmpeg,
--               mkvtoolnix, etc.) before a script shells out to it, so a
--               fresh Script-Server container can recover from "command
--               not found" on first run instead of just failing. Same
--               idea as shared/ensure_module.lua, but for PATH binaries
--               instead of require()'able Lua modules -- not a
--               standalone Script-Server script, a helper loaded via
--               dofile().
--
--               Usage (relative to the calling script, so it also works
--               standalone outside the container):
--                 local SHARED_DIR = ((arg and arg[0] or ""):match("^(.*)/") or ".") .. "/shared/"
--                 local ensure_bin_ok, ensure_bin =
--                     pcall(dofile, SHARED_DIR .. "ensure_binary.lua")
--                 if ensure_bin_ok then
--                     ensure_bin.ensure("mkvpropedit", "apt-get install -y mkvtoolnix")
--                 end
--
-- Version : 1.0.1
-- Date    : 2026-11-12
--
-- Platform file: shipped by the Script-Server image (tools/PLATFORM_FILES)
-- and refreshed on every start - don't copy it into a sibling repo, and
-- don't edit it on the NAS. Originally ss_movie_file_management's.
-- ============================================================

local M = {}

local function on_path(bin_name)
    local handle = io.popen("command -v " .. bin_name .. " 2>/dev/null")
    local path = handle and handle:read("*a") or ""
    if handle then handle:close() end
    return path ~= ""
end

-- ensure(bin_name, install_cmd): checks `command -v bin_name`, and if
-- missing, runs install_cmd via the shell and checks again. install_cmd's
-- combined stdout+stderr is echoed to stderr either way, so failures are
-- visible in Script-Server's live output, not swallowed.
function M.ensure(bin_name, install_cmd)
    if on_path(bin_name) then return true end

    io.stderr:write(string.format(
        "[SETUP] Binary '%s' not found -- attempting to install...\n", bin_name))
    io.stderr:write("[SETUP]   $ " .. install_cmd .. "\n")
    io.stderr:flush()

    local handle = io.popen("(" .. install_cmd .. ") 2>&1")
    local log = handle and handle:read("*a") or ""
    if handle then handle:close() end
    if log ~= "" then io.stderr:write(log) end

    if not on_path(bin_name) then
        io.stderr:write(string.format(
            "[SETUP] FAILED to install '%s' automatically.\n", bin_name))
        io.stderr:write(
            "[SETUP] This container may lack network access to apt mirrors,\n" ..
            "[SETUP] or root permissions. Install manually and re-run:\n" ..
            "[SETUP]   " .. install_cmd .. "\n")
        os.exit(1)
    end

    io.stderr:write(string.format("[SETUP] '%s' installed successfully.\n", bin_name))
    io.stderr:flush()
    return true
end

return M
