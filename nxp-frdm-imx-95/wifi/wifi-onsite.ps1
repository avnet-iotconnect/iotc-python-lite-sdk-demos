<#
.SYNOPSIS
  Push wifi-setup.sh to FRDM i.MX95 boards over their USB debug serial port and run it.
  With no -Port, every attached board is detected automatically (CH344 quad-UART, port A = Linux console)
  and configured one after another.
.EXAMPLE
  .\wifi-onsite.ps1 -SSID 'MyNet' -Pass 'MyPassphrase'          # all attached boards
  .\wifi-onsite.ps1 -Port COM24 -SSID 'MyNet' -Pass 'MyPassphrase'
  .\wifi-onsite.ps1 -List                                       # show detected boards
  .\wifi-onsite.ps1 -Status
  .\wifi-onsite.ps1 -Port COM24 -Remove
#>
param(
    [string]$Port,
    [string]$SSID,
    [string]$Pass,
    [switch]$Status,
    [switch]$Remove,
    [switch]$List,
    [string]$Script = (Join-Path $PSScriptRoot 'wifi-setup.sh')
)
$ErrorActionPreference = 'Stop'

# --- board discovery: FRDM i.MX95 debug MCU = WCH CH344, VID 1A86 PID 55D5; MI_00 (SERIAL-A) is the A55 console
function Find-BoardPorts {
    Get-CimInstance Win32_PnPEntity |
        Where-Object { $_.PNPDeviceID -match 'VID_1A86&PID_55D5&MI_00' -and $_.Name -match '\((COM\d+)\)' } |
        ForEach-Object { if ($_.Name -match '\((COM\d+)\)') { $Matches[1] } } |
        Sort-Object { [int]($_ -replace 'COM','') }
}

if ($List) {
    $ports = @(Find-BoardPorts)
    if (-not $ports) { Write-Host "No FRDM i.MX95 boards detected (looking for CH344 SERIAL-A ports)."; exit 1 }
    Write-Host "Detected boards (console port): $($ports -join ', ')"
    exit 0
}
if (-not ($Status -or $Remove) -and -not $SSID) { throw "Give -SSID (and -Pass), or -Status / -Remove / -List" }

# --- payload: normalise to LF so busybox sh accepts it, hash the exact bytes we send
$bytes = [IO.File]::ReadAllBytes($Script)
$text  = [Text.Encoding]::UTF8.GetString($bytes) -replace "`r`n", "`n"
$bytes = [Text.Encoding]::UTF8.GetBytes($text)
$sha   = ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($bytes)) -replace '-','').ToLower()
$b64   = [Convert]::ToBase64String($bytes)

function Invoke-Board([string]$Port) {
    $p = New-Object System.IO.Ports.SerialPort $Port,115200,None,8,One
    $p.ReadTimeout = 500; $p.DtrEnable = $true; $p.RtsEnable = $true
    $p.Open()
    function Drain([int]$ms) {
        $sw = [Diagnostics.Stopwatch]::StartNew(); $out = ''
        while ($sw.ElapsedMilliseconds -lt $ms) { try { $out += $p.ReadExisting() } catch {}; Start-Sleep -m 50 }
        return $out
    }
    function WaitPrompt([int]$timeoutS) {
        $sw = [Diagnostics.Stopwatch]::StartNew(); $out = ''
        while ($sw.Elapsed.TotalSeconds -lt $timeoutS) {
            try { $out += $p.ReadExisting() } catch {}
            if ($out -match "(?m)^root@\S+:\S+# *$") { return $out }
            Start-Sleep -m 100
        }
        return $out
    }
    function Send([string]$line) { $p.Write("$line`r"); Start-Sleep -m 60 }

    try {
        # wait for a login prompt or shell (board may still be booting: ~60 s from power-on).
        # Send ONE newline up front to wake an idle prompt, then wait passively: any keystroke that lands in
        # U-Boot's autoboot countdown drops the board to the u-boot=> prompt. If that happens anyway, type 'boot'.
        $p.DiscardInBuffer(); Send ''
        $banner = Drain 1500
        $boot = [Diagnostics.Stopwatch]::StartNew(); $said = $false; $kicked = $false
        while ($banner -notmatch 'login:' -and $banner -notmatch 'root@' -and $boot.Elapsed.TotalSeconds -lt 120) {
            if (-not $said) { Write-Host "[$Port] waiting for boot..."; $said = $true }
            if ($banner -match '(?m)^u-boot=> *$' -and -not $kicked) {
                Write-Host "[$Port] board stopped at U-Boot prompt, resuming boot"
                Send 'boot'; $kicked = $true; $banner = ''
            }
            $banner += Drain 3000
        }
        if ($banner -match 'login:') { Send 'root'; $banner += WaitPrompt 20 }
        if ($banner -notmatch 'root@') { Send ''; $banner += WaitPrompt 5 }
        if ($banner -notmatch 'root@') { Write-Host "[$Port] no root shell after 120 s (no power? SW1 in SDP? wrong port?)" -ForegroundColor Red; return 3 }
        $host_ = if ($banner -match 'root@(\S+?):') { $Matches[1] } else { '?' }
        Write-Host "[$Port] shell on $host_"

        # transfer script as base64, verify sha256; a board still busy booting can drop console bytes,
        # so retry up to 3x with smaller chunks and longer gaps each time
        $ok = $false
        foreach ($attempt in 1..3) {
            $chunk = @(76, 48, 32)[$attempt - 1]; $gap = @(60, 120, 200)[$attempt - 1]
            $p.DiscardInBuffer()
            Send "cat > /tmp/wifi-setup.b64 <<'B64EOF'"
            for ($i = 0; $i -lt $b64.Length; $i += $chunk) {
                $p.Write($b64.Substring($i, [Math]::Min($chunk, $b64.Length - $i)) + "`r"); Start-Sleep -m $gap
            }
            Send 'B64EOF'
            $null = Drain 800; $p.DiscardInBuffer()
            Send "base64 -d /tmp/wifi-setup.b64 > /tmp/wifi-setup.sh && sha256sum /tmp/wifi-setup.sh"
            $r = WaitPrompt 10
            if ($r -match $sha) { $ok = $true; break }
            Write-Host "[$Port] transfer corrupted (attempt $attempt), retrying slower..." -ForegroundColor Yellow
            Start-Sleep -Seconds 3
        }
        if (-not $ok) { Write-Host "[$Port] transfer corrupted 3 times, giving up" -ForegroundColor Red; return 4 }
        Write-Host "[$Port] script transferred and verified"

        $p.DiscardInBuffer()
        if ($Status)      { Send 'sh /tmp/wifi-setup.sh --status'; $r = WaitPrompt 15 }
        elseif ($Remove)  { Send 'sh /tmp/wifi-setup.sh --remove'; $r = WaitPrompt 20 }
        else {
            $q = { param($s) "'" + ($s -replace "'", "'\''") + "'" }
            $cmd = "sh /tmp/wifi-setup.sh $(& $q $SSID)"
            if ($Pass) { $cmd += " $(& $q $Pass)" }
            Send $cmd
            $r = WaitPrompt 75
        }
        $lines = ($r -split "`n") | ForEach-Object { $_.TrimEnd("`r") } |
                 Where-Object { $_ -notmatch '^sh /tmp/wifi-setup' -and $_ -notmatch '^root@' -and $_ -ne '' }
        $lines | ForEach-Object { Write-Host "  $_" }
        if ($r -match 'WIFI OK')         { Write-Host "[$Port] $host_ : SUCCESS" -ForegroundColor Green; return 0 }
        elseif ($r -match 'WIFI FAILED') { Write-Host "[$Port] $host_ : FAILED" -ForegroundColor Red; return 2 }
        return 0
    } finally { $p.Close() }
}

$ports = if ($Port) { @($Port) } else { @(Find-BoardPorts) }
if (-not $ports) { Write-Host "No FRDM i.MX95 boards detected and no -Port given." -ForegroundColor Red; exit 1 }
if (-not $Port) { Write-Host "Detected boards on: $($ports -join ', ')" }

$worst = 0
foreach ($pt in $ports) {
    try { $rc = Invoke-Board $pt } catch { Write-Host "[$pt] error: $($_.Exception.Message)" -ForegroundColor Red; $rc = 5 }
    if ($rc -gt $worst) { $worst = $rc }
}
if ($ports.Count -gt 1) { Write-Host "Done: $($ports.Count) boards, worst exit code $worst" }
exit $worst
