#!/usr/bin/env lua5.1
-- Name: network_scanner.lua
-- Version: 1.2.0
-- Description: Multi-method LAN scanner - nmap ping scan, arp-scan, nmap
--              service detection, and the local ARP cache - with a small
--              built-in OUI vendor lookup. REQUIRES the container to run
--              with network_mode: host (see docker-compose.yml); otherwise
--              it only sees Docker's internal bridge network, not your LAN.
--              Also merges results into the persistent device inventory
--              (/app/data/network_inventory.json, see label_device.py and
--              view_inventory.py) unless disabled. Run standalone
--              (./network_scanner.lua --subnet 192.168.1.0/24) or from
--              Script-Server.

local function getenv_bool(name, default)
  local v = os.getenv(name)
  if v == nil or v == '' then return default end
  return v == 'true' or v == '1'
end

local subnet = os.getenv('PARAM_SUBNET') or ''
local verbose = getenv_bool('PARAM_VERBOSE', true)
local debug = os.getenv('DEBUG') == 'true'

local enable_nmap_ping = getenv_bool('PARAM_SCAN_NMAP_PING', true)
local enable_arp_scan = getenv_bool('PARAM_SCAN_ARP_SCAN', true)
local enable_service_scan = getenv_bool('PARAM_SCAN_SERVICE_DETECTION', false)
local enable_arp_cache = getenv_bool('PARAM_SCAN_ARP_CACHE', true)
local export_csv = getenv_bool('PARAM_EXPORT_CSV', false)
local update_inventory = getenv_bool('PARAM_UPDATE_INVENTORY', true)

local i = 1
while i <= #arg do
  local a = arg[i]
  if a == '--subnet' and arg[i + 1] then
    subnet = arg[i + 1]; i = i + 2
  elseif a == '--no-verbose' then
    verbose = false; i = i + 1
  elseif a == '--debug' then
    debug = true; i = i + 1
  elseif a == '--no-nmap-ping' then
    enable_nmap_ping = false; i = i + 1
  elseif a == '--no-arp-scan' then
    enable_arp_scan = false; i = i + 1
  elseif a == '--service-scan' then
    enable_service_scan = true; i = i + 1
  elseif a == '--no-arp-cache' then
    enable_arp_cache = false; i = i + 1
  elseif a == '--export-csv' then
    export_csv = true; i = i + 1
  elseif a == '--no-update-inventory' then
    update_inventory = false; i = i + 1
  else
    i = i + 1
  end
end

if subnet == '' then
  print('Missing required subnet (e.g. --subnet 192.168.1.0/24)')
  os.exit(1)
end

-- Color codes for terminal output
local colors = {
    reset = "\27[0m",
    bold = "\27[1m",
    red = "\27[31m",
    green = "\27[32m",
    yellow = "\27[33m",
    blue = "\27[34m",
    cyan = "\27[36m"
}

-- Device database for common MAC address prefixes (OUI - Organizationally Unique Identifier)
local oui_db = {
    ["00:50:56"] = "VMware",
    ["00:0C:29"] = "VMware",
    ["00:05:69"] = "VMware",
    ["08:00:27"] = "VirtualBox",
    ["52:54:00"] = "QEMU/KVM",
    ["B8:27:EB"] = "Raspberry Pi Foundation",
    ["DC:A6:32"] = "Raspberry Pi Foundation",
    ["E4:5F:01"] = "Raspberry Pi Foundation",
    ["00:1A:11"] = "Google",
    ["3C:5A:B4"] = "Google",
    ["F4:F5:D8"] = "Google",
    ["AC:63:BE"] = "Amazon Technologies",
    ["FC:A6:67"] = "Amazon Technologies",
    ["00:FC:8B"] = "Amazon Technologies",
    ["44:65:0D"] = "Amazon Technologies",
    ["00:17:88"] = "Philips Hue",
    ["EC:FA:BC"] = "Philips Hue",
    ["00:0D:B9"] = "Netgear",
    ["A0:63:91"] = "Netgear",
    ["E0:46:9A"] = "Netgear",
    ["00:50:F2"] = "Microsoft",
    ["00:15:5D"] = "Microsoft Hyper-V",
    ["28:6A:BA"] = "Apple",
    ["A4:83:E7"] = "Apple",
    ["98:01:A7"] = "Apple",
    ["B8:78:2E"] = "Apple",
    ["00:25:00"] = "Apple",
    ["00:1C:B3"] = "Apple"
}

-- Function to identify device type from MAC prefix
local function identify_vendor(mac)
    if not mac then return "Unknown" end
    local prefix = mac:sub(1, 8):upper()
    return oui_db[prefix] or "Unknown Vendor"
end

-- Debug print helper
local function debug_print(msg)
    if debug then
        print(colors.yellow .. "[DEBUG] " .. msg .. colors.reset)
    end
end

-- Function to run a command and return output
local function run_command(cmd)
    local handle = io.popen(cmd .. " 2>&1")
    if not handle then return nil end
    local result = handle:read("*a")
    local success = handle:close()
    return result, success
end

-- Function to check if a command exists
local function command_exists(cmd)
    local result = run_command("which " .. cmd .. " 2>/dev/null")
    return result and result ~= "" and not result:match("not found")
end

-- Device storage
local devices = {}

print(colors.bold .. colors.cyan .. "=== Enhanced Network Scanner ===" .. colors.reset)
print(colors.yellow .. "Target subnet: " .. subnet .. colors.reset)
print("")

-- Scan Method 1: Nmap Ping Scan (Fast discovery)
if enable_nmap_ping then
    print(colors.bold .. "[1/4] Running Nmap Ping Scan..." .. colors.reset)

    -- Try privileged scan first (gets MAC addresses), fallback to unprivileged
    local nmap_command = "nmap -sn -PR " .. subnet .. " -oG - 2>/dev/null || nmap -sn " .. subnet .. " -oG -"
    debug_print("Command: " .. nmap_command)
    local result = run_command(nmap_command)

    if result then
        debug_print("Nmap output length: " .. #result .. " bytes")
        if debug then
            print(colors.yellow .. "[DEBUG] First 500 chars of output:" .. colors.reset)
            print(result:sub(1, 500))
            print(colors.yellow .. "[DEBUG] ---" .. colors.reset)
        end

        local count = 0
        for line in result:gmatch("[^\r\n]+") do
            if line:match("Host: ") then
                local ip = line:match("Host: ([%d.]+)")
                local mac = line:match("MAC Address: ([%xA-F:]+)")
                local hostname = line:match("%((.-)%)")

                if ip then
                    count = count + 1
                    devices[ip] = devices[ip] or {}
                    devices[ip].ip = ip
                    devices[ip].mac = mac
                    devices[ip].hostname = hostname
                    devices[ip].methods = devices[ip].methods or {}
                    table.insert(devices[ip].methods, "nmap-ping")
                    debug_print("Found device: " .. ip .. " | MAC: " .. (mac or "none") .. " | Host: " .. (hostname or "none"))
                end
            end
        end

        if count > 0 and not result:match("MAC Address:") then
            debug_print("Note: No MAC addresses in scan - likely scanning from this host")
            debug_print("MAC addresses require root privileges or ARP scan")
        end

        debug_print("Nmap ping scan found " .. count .. " devices")
        print(colors.green .. "✓ Ping scan complete (" .. count .. " devices)" .. colors.reset)
    else
        print(colors.red .. "✗ Nmap ping scan failed" .. colors.reset)
    end
else
    print(colors.yellow .. "[1/4] Nmap Ping Scan disabled" .. colors.reset)
end

-- Scan Method 2: ARP Scan (if available)
if enable_arp_scan then
    local arp_scan_available = command_exists("arp-scan")
    debug_print("arp-scan available: " .. tostring(arp_scan_available))

    if arp_scan_available then
        print(colors.bold .. "[2/4] Running ARP Scan..." .. colors.reset)

        debug_print("Detecting network interface...")
        local ifconfig_result = run_command("ip addr show 2>/dev/null || ifconfig")
        debug_print("Network interfaces detected")

        local interface = nil
        local interface_ip = nil

        local subnet_prefix = subnet:match("^([%d.]+)%.")
        debug_print("Looking for interface on subnet: " .. subnet_prefix .. ".x")

        for line in ifconfig_result:gmatch("[^\r\n]+") do
            local iface = line:match("^(%w+):")
            if iface then
                interface = iface
            end
            local ip = line:match("inet%s+([%d.]+)")
            if ip and ip:match("^" .. subnet_prefix:gsub("%.", "%%.")) then
                interface_ip = ip
                debug_print("Found matching interface: " .. (interface or "unknown") .. " with IP: " .. ip)
                break
            end
        end

        local arp_result = nil
        local arp_count = 0

        debug_print("Trying arp-scan with explicit subnet (no sudo)")
        local arp_cmd = "arp-scan " .. subnet .. " --retry=3 2>&1"
        debug_print("Command: " .. arp_cmd)
        arp_result = run_command(arp_cmd)

        if debug and arp_result then
            print(colors.yellow .. "[DEBUG] ARP-scan output (first 800 chars):" .. colors.reset)
            print(arp_result:sub(1, 800))
            print(colors.yellow .. "[DEBUG] ---" .. colors.reset)
        end

        if (not arp_result or arp_result:match("ERROR") or arp_result:match("WARNING.*Could not obtain IP")) and interface and interface_ip then
            debug_print("Trying arp-scan with interface: " .. interface)
            arp_cmd = "arp-scan --interface=" .. interface .. " --localnet --retry=3 2>&1"
            debug_print("Command: " .. arp_cmd)
            arp_result = run_command(arp_cmd)

            if debug and arp_result then
                print(colors.yellow .. "[DEBUG] ARP-scan interface output (first 800 chars):" .. colors.reset)
                print(arp_result:sub(1, 800))
                print(colors.yellow .. "[DEBUG] ---" .. colors.reset)
            end
        end

        if arp_result and not arp_result:match("ERROR") then
            for line in arp_result:gmatch("[^\r\n]+") do
                local ip, mac, vendor = line:match("([%d.]+)%s+([%x:]+)%s+(.+)")
                if ip and mac then
                    arp_count = arp_count + 1
                    devices[ip] = devices[ip] or {}
                    devices[ip].ip = ip
                    devices[ip].mac = mac
                    devices[ip].arp_vendor = vendor
                    devices[ip].methods = devices[ip].methods or {}
                    table.insert(devices[ip].methods, "arp-scan")
                    debug_print("ARP found: " .. ip .. " | MAC: " .. mac .. " | Vendor: " .. vendor)
                end
            end
            print(colors.green .. "✓ ARP scan complete (" .. arp_count .. " devices)" .. colors.reset)
        else
            print(colors.red .. "✗ ARP scan failed" .. colors.reset)
            if arp_result then
                local error_msg = arp_result:match("ERROR:([^\n]+)") or arp_result:match("WARNING:([^\n]+)") or "Unknown error"
                print(colors.yellow .. "  Error: " .. error_msg .. colors.reset)
                print(colors.yellow .. "  Tip: Try running as root or check interface configuration" .. colors.reset)
            end
        end
    else
        print(colors.yellow .. "[2/4] Skipping ARP Scan (arp-scan not installed)" .. colors.reset)
    end
else
    print(colors.yellow .. "[2/4] ARP Scan disabled" .. colors.reset)
end

-- Scan Method 3: Nmap Service Detection (slower but more detailed)
if enable_service_scan then
    print(colors.bold .. "[3/4] Running Service Detection Scan..." .. colors.reset)
    local service_command = "nmap -sV -T4 --top-ports 100 " .. subnet .. " -oG -"
    debug_print("Command: " .. service_command)
    local service_result = run_command(service_command)

    if service_result then
        debug_print("Service scan output length: " .. #service_result .. " bytes")
        local current_ip = nil
        local service_count = 0

        for line in service_result:gmatch("[^\r\n]+") do
            if line:match("Host: ") then
                current_ip = line:match("Host: ([%d.]+)")
                local mac = line:match("MAC Address: ([%x:]+)")
                local hostname = line:match("%((.-)%)")

                if current_ip and devices[current_ip] then
                    service_count = service_count + 1
                    devices[current_ip].mac = devices[current_ip].mac or mac
                    devices[current_ip].hostname = devices[current_ip].hostname or hostname
                    devices[current_ip].services = {}
                    table.insert(devices[current_ip].methods, "nmap-service")
                    debug_print("Service scan processing: " .. current_ip)
                end
            elseif line:match("Ports: ") and current_ip and devices[current_ip] then
                local ports_info = line:match("Ports: (.+)")
                if ports_info then
                    for port_entry in ports_info:gmatch("([^,]+)") do
                        local port, state, service = port_entry:match("(%d+)/([^/]+)/[^/]+/[^/]+/([^/]+)")
                        if port and state == "open" then
                            table.insert(devices[current_ip].services, service .. "(" .. port .. ")")
                            debug_print("  Found service: " .. service .. " on port " .. port)
                        end
                    end
                end
            end
        end
        debug_print("Service scan processed " .. service_count .. " devices")
        print(colors.green .. "✓ Service detection complete" .. colors.reset)
    else
        print(colors.red .. "✗ Service detection failed" .. colors.reset)
    end
else
    print(colors.yellow .. "[3/4] Service Detection Scan disabled" .. colors.reset)
end

-- Scan Method 4: Check ARP cache
if enable_arp_cache then
    print(colors.bold .. "[4/4] Checking ARP Cache..." .. colors.reset)

    local arp_cache = run_command("ip neigh show 2>/dev/null || ip neighbor show 2>/dev/null || arp -a 2>/dev/null || arp -an 2>/dev/null")

    if arp_cache and arp_cache ~= "" and not arp_cache:match("not found") then
        debug_print("ARP cache output length: " .. #arp_cache .. " bytes")
        if debug then
            print(colors.yellow .. "[DEBUG] ARP cache output (first 500 chars):" .. colors.reset)
            print(arp_cache:sub(1, 500))
            print(colors.yellow .. "[DEBUG] ---" .. colors.reset)
        end

        local cache_count = 0
        for line in arp_cache:gmatch("[^\r\n]+") do
            local ip, mac = nil, nil

            ip = line:match("^([%d.]+)%s+")
            if ip then
                mac = line:match("lladdr%s+([%x:]+)")
            end

            if not ip or not mac then
                local hostname
                hostname, ip, mac = line:match("([%w.-]+)%s+%(([%d.]+)%)%s+at%s+([%x:]+)")
                if hostname and ip and devices[ip] and not devices[ip].hostname then
                    devices[ip].hostname = hostname
                end
            end

            if not ip or not mac then
                ip, mac = line:match("%(([%d.]+)%)%s+at%s+([%x:]+)")
            end

            if not ip or not mac then
                ip, mac = line:match("([%d.]+)%s+[%w]+%s+([%x:]+)")
            end

            -- Require a clean IPv4 dotted-quad: ip neigh show also lists IPv6
            -- neighbors (fe80::..., multicast, etc.), and the loose regexes
            -- above can occasionally grab a partial match out of those lines.
            if ip and mac and ip:match("^%d+%.%d+%.%d+%.%d+$") then
                cache_count = cache_count + 1
                devices[ip] = devices[ip] or {}
                devices[ip].ip = ip
                devices[ip].mac = devices[ip].mac or mac
                devices[ip].methods = devices[ip].methods or {}
                table.insert(devices[ip].methods, "arp-cache")
                debug_print("ARP cache entry: " .. ip .. " | MAC: " .. mac)
            end
        end
        debug_print("Found " .. cache_count .. " entries in ARP cache")
        print(colors.green .. "✓ ARP cache checked (" .. cache_count .. " entries)" .. colors.reset)
    else
        print(colors.yellow .. "⚠ Could not read ARP cache (no compatible command found)" .. colors.reset)
        debug_print("Tried: ip neigh, ip neighbor, arp -a, arp -an")
    end
else
    print(colors.yellow .. "[4/4] ARP Cache check disabled" .. colors.reset)
end

-- Display results
print("")
print(colors.bold .. colors.cyan .. "=== Scan Summary ===" .. colors.reset)

local method_stats = {
    ["nmap-ping"] = 0,
    ["arp-scan"] = 0,
    ["nmap-service"] = 0,
    ["arp-cache"] = 0
}

local devices_with_mac = 0
local devices_with_hostname = 0
local devices_with_services = 0

for ip, device in pairs(devices) do
    if device.mac then devices_with_mac = devices_with_mac + 1 end
    if device.hostname and device.hostname ~= "" then devices_with_hostname = devices_with_hostname + 1 end
    if device.services and #device.services > 0 then devices_with_services = devices_with_services + 1 end

    if device.methods then
        for _, method in ipairs(device.methods) do
            if method_stats[method] then
                method_stats[method] = method_stats[method] + 1
            end
        end
    end
end

print("Devices found by method:")
print("  Nmap Ping Scan:     " .. method_stats["nmap-ping"] .. " devices")
print("  ARP Scan:           " .. method_stats["arp-scan"] .. " devices")
print("  Service Detection:  " .. method_stats["nmap-service"] .. " devices")
print("  ARP Cache:          " .. method_stats["arp-cache"] .. " devices")
print("")
print("Device information collected:")
print("  With MAC addresses: " .. devices_with_mac .. " devices")
print("  With hostnames:     " .. devices_with_hostname .. " devices")
print("  With services:      " .. devices_with_services .. " devices")
print("")

print(colors.bold .. colors.cyan .. "=== Discovered Devices ===" .. colors.reset)
print("")

local device_count = 0
local sorted_ips = {}
for ip in pairs(devices) do
    table.insert(sorted_ips, ip)
end
table.sort(sorted_ips, function(a, b)
    local a_parts = {a:match("(%d+)%.(%d+)%.(%d+)%.(%d+)")}
    local b_parts = {b:match("(%d+)%.(%d+)%.(%d+)%.(%d+)")}
    -- Fall back to plain string comparison if either side isn't a clean
    -- IPv4 dotted-quad, so a stray value can never crash the sort.
    if (#a_parts < 4) or (#b_parts < 4) then
        return a < b
    end
    for i2 = 1, 4 do
        if tonumber(a_parts[i2]) ~= tonumber(b_parts[i2]) then
            return tonumber(a_parts[i2]) < tonumber(b_parts[i2])
        end
    end
    return false
end)

for _, ip in ipairs(sorted_ips) do
    local device = devices[ip]
    device_count = device_count + 1

    print(colors.bold .. colors.green .. "Device #" .. device_count .. colors.reset)
    print("  IP Address:    " .. colors.cyan .. ip .. colors.reset)

    if device.mac then
        local vendor = identify_vendor(device.mac)
        print("  MAC Address:   " .. colors.yellow .. device.mac .. colors.reset)
        if device.arp_vendor then
            print("  Vendor:        " .. colors.blue .. device.arp_vendor .. colors.reset)
        elseif vendor ~= "Unknown Vendor" then
            print("  Vendor:        " .. colors.blue .. vendor .. " (from OUI)" .. colors.reset)
        end
    else
        print("  MAC Address:   " .. colors.red .. "Unknown (possibly host machine)" .. colors.reset)
    end

    if device.hostname then
        print("  Hostname:      " .. device.hostname)
    end

    if device.services and #device.services > 0 then
        print("  Services:      " .. table.concat(device.services, ", "))
    end

    if verbose and device.methods then
        print("  Detected by:   " .. table.concat(device.methods, ", "))
    end

    print("")
end

print(colors.bold .. "Total devices found: " .. device_count .. colors.reset)
print(colors.cyan .. "==========================" .. colors.reset)

local function write_csv(path)
    local csv_file = io.open(path, "w")
    if not csv_file then
        return false
    end
    csv_file:write("IP,MAC,Hostname,Vendor,Services\n")
    for _, ip in ipairs(sorted_ips) do
        local device = devices[ip]
        local mac = device.mac or ""
        local hostname = device.hostname or ""
        local vendor = device.arp_vendor or identify_vendor(device.mac)
        local services = device.services and table.concat(device.services, "; ") or ""
        csv_file:write(string.format("%s,%s,%s,%s,%s\n", ip, mac, hostname, vendor, services))
    end
    csv_file:close()
    return true
end

if export_csv then
    local out_dir = "/app/data/network_scans"
    os.execute("mkdir -p " .. out_dir)
    local csv_path = out_dir .. "/scan_" .. os.time() .. ".csv"
    if write_csv(csv_path) then
        print(colors.green .. "\n✓ Results exported to " .. csv_path .. colors.reset)
    else
        print(colors.red .. "\n✗ Failed to write CSV to " .. csv_path .. colors.reset)
    end
end

if update_inventory then
    local tmp_csv = "/tmp/network_scan_" .. os.time() .. ".csv"
    if write_csv(tmp_csv) then
        local merge_output = run_command("python3 /app/scripts/shared/merge_inventory.py " .. tmp_csv)
        os.remove(tmp_csv)
        print("")
        if merge_output then
            io.write(merge_output)
        end
    else
        print(colors.red .. "\n✗ Failed to prepare inventory update" .. colors.reset)
    end
end
