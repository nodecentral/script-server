-- ============================================================
-- shared/ensure_module.lua
-- ============================================================
-- Description : Self-installs a missing Lua module before require()'ing
--               it, so a fresh Script-Server container can recover from
--               a bare "module 'x' not found" error on first run instead
--               of just failing outright. Not a standalone Script-Server
--               script -- a helper loaded via dofile(), the same pattern
--               as the other scripts/shared/ helpers.
--
--               Usage (relative to the calling script, so it also works
--               standalone outside the container):
--                 local SHARED_DIR = ((arg and arg[0] or ""):match("^(.*)/") or ".") .. "/shared/"
--                 local ensure_ok, ensure =
--                     pcall(dofile, SHARED_DIR .. "ensure_module.lua")
--                 local sqlite3
--                 if ensure_ok then
--                     sqlite3 = ensure.ensure("lsqlite3", "luarocks install lsqlite3")
--                 else
--                     sqlite3 = require("lsqlite3")  -- last resort, errors loudly if missing
--                 end
--
-- Version : 1.2.0
-- Date    : 2026-11-12
--
-- Platform file: shipped by the Script-Server image (tools/PLATFORM_FILES)
-- and refreshed on every start - don't copy it into a sibling repo, and
-- don't edit it on the NAS. Originally ss_movie_file_management's.
-- ============================================================

local M = {}

-- Script-Server runs scripts as PUID (not root) on the NAS. Since image 2.3.0 that still works:
-- apt-get goes through sudo, luarocks installs into /app/data/.deps (see tools/rootless/ in
-- nodecentral/script-server). If an install fails as non-root anyway, say what to check.
local function current_uid()
    local handle = io.popen("id -u 2>/dev/null")
    local uid = handle and handle:read("*l") or ""
    if handle then handle:close() end
    return tonumber(uid)
end

local function non_root_hint()
    local uid = current_uid()
    if not uid or uid == 0 then return "" end
    return string.format(
        "[SETUP] (Running as uid %d. Script Server 2.3.0+ lets scripts install packages\n" ..
        "[SETUP] without root; an older image, or ALLOW_APT=false on the container, can't.)\n",
        uid)
end

-- ensure(name, install_cmd): require(name), or if that fails, run
-- install_cmd via the shell and retry once. install_cmd's combined
-- stdout+stderr is echoed to stderr either way, so failures are visible
-- in Script-Server's live output, not swallowed.
function M.ensure(name, install_cmd)
    local ok, mod = pcall(require, name)
    if ok then return mod end

    io.stderr:write(string.format(
        "[SETUP] Module '%s' not found -- attempting to install...\n", name))
    io.stderr:write("[SETUP]   $ " .. install_cmd .. "\n")

    local handle = io.popen("(" .. install_cmd .. ") 2>&1")
    local log = handle and handle:read("*a") or ""
    if handle then handle:close() end
    if log ~= "" then io.stderr:write(log) end

    ok, mod = pcall(require, name)
    if not ok then
        io.stderr:write(string.format(
            "[SETUP] FAILED to install '%s' automatically. Error: %s\n",
            name, tostring(mod)))
        io.stderr:write(
            "[SETUP] This container may lack network access to apt/LuaRocks\n" ..
            "[SETUP] mirrors, or permission to install. Install manually and re-run:\n" ..
            "[SETUP]   " .. install_cmd .. "\n" .. non_root_hint())
        os.exit(1)
    end

    io.stderr:write(string.format("[SETUP] '%s' installed successfully.\n", name))
    return mod
end

return M
