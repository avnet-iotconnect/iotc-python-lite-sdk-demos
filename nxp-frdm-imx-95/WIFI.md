# WiFi Setup for the NXP FRDM-i.MX95 (whinlatter BSP / golden image)

The board's on-module IW612 WiFi works out of the box at the driver level (the `moal` module autoloads at boot
and `mlan0` is present), but **connman cannot drive it**: the BSP's `wpa_supplicant` (v2.11-M005) is built
without D-Bus support, so `wpa_supplicant.service` exits at every boot and `connmanctl enable wifi` answers
`wifi is not available`. The classic connmanctl walkthrough therefore does not work on this image.

The supported method is to run `wpa_supplicant` directly on `mlan0` plus `udhcpc`, wrapped in a systemd unit so
it survives reboots. Everything below is scripted in [wifi/wifi-setup.sh](wifi/wifi-setup.sh). Ethernet keeps
working alongside WiFi (connman still manages `eth0`/`eth1`).

> Applies to every board flashed from the golden image (v1.0.2 … v1.0.4) and to a fresh whinlatter flash.
> Nothing here needs the board to have Internet first.

---

## Option A: onsite, over the USB debug serial port (no network needed)

This is the fleet path. Each board is done in about 30 s from a Windows PC with nothing but the USB debug
cable, the same connection used for the serial console.

Each board's debug MCU enumerates as a **WCH CH344 quad UART** (four `USB-Enhanced-SERIAL-x CH344` COM ports);
port **A** is the Linux console. Windows hands out different COM numbers per board and per USB socket, so the
helper finds the console port(s) itself; you never have to look them up.

1. Connect each board's **DEBUG USB** port to the PC (directly or via a hub) and power the boards. Wait for
   the login prompt (about 60 s after power-on).
2. Run, from anywhere (or `cd C:\dev\iotc-python-lite-sdk-demos` first and drop the leading path):

   ```powershell
   C:\dev\iotc-python-lite-sdk-demos\nxp-frdm-imx-95\wifi\wifi-onsite.ps1 -SSID 'YourNetwork' -Pass 'YourPassphrase'
   ```

   With no `-Port`, every attached board is detected and configured in turn. The helper logs in as root over
   the serial console (no password), pushes `wifi-setup.sh` as base64, verifies its SHA-256 on the board, runs
   it, and prints the result per board:

   ```
   Detected boards on: COM24, COM31
   [COM24] shell on imx95-55ea
   [COM24] script transferred and verified
     connecting to 'YourNetwork' ...
     WIFI OK: YourNetwork -> 192.168.68.90/22
     --- mlan0 ---
     ssid=YourNetwork
     wpa_state=COMPLETED
     ip_address=192.168.68.90
     unit: enabled
   [COM24] imx95-55ea : SUCCESS
   [COM31] ...
   Done: 2 boards, worst exit code 0
   ```

   Exit code 0 = connected and persisted; 2 = wrong SSID/passphrase or no DHCP within 60 s (the unit is still
   installed and will keep retrying, so re-run with corrected credentials); 3 = no root shell on that port
   (board still booting, or a non-console port was forced with `-Port`).
3. Unplug, plug in the next batch, repeat. Other helper modes:

   ```powershell
   wifi-onsite.ps1 -List                    # show the console COM port of every attached board
   wifi-onsite.ps1 -Status                  # association + IP, all boards
   wifi-onsite.ps1 -Port COM24 -Remove      # disable and delete the unit on one board
   ```

`-Port COMxx` restricts any mode to a single board.

## Option B: over SSH or a serial terminal by hand

If the board is already reachable (Ethernet), copy the script and run it:

```bash
scp wifi/wifi-setup.sh root@<board-ip>:/tmp/
ssh root@<board-ip> sh /tmp/wifi-setup.sh 'YourNetwork' 'YourPassphrase'
```

Or paste the equivalent commands into a serial terminal (PuTTY/TeraTerm, 115200 8N1):

```bash
# credentials (replaces the stock open-network block)
{ printf 'ctrl_interface=/var/run/wpa_supplicant\nctrl_interface_group=0\nupdate_config=1\n\n'
  wpa_passphrase 'YourNetwork' 'YourPassphrase' | grep -v '#psk'; } > /etc/wpa_supplicant.conf
chmod 600 /etc/wpa_supplicant.conf

# bring it up now
ip link set mlan0 up
wpa_supplicant -B -Dnl80211 -imlan0 -c/etc/wpa_supplicant.conf
udhcpc -b -i mlan0

# verify
wpa_cli -i mlan0 status | grep -E 'ssid|wpa_state|ip_address'
ping -c 3 8.8.8.8
```

For persistence across reboots, run `sh wifi-setup.sh SSID PASS` anyway (it writes and enables
`/etc/systemd/system/wifi-mlan0.service`), or create that unit by hand with the same three commands as
`ExecStartPre`/`ExecStart`/`ExecStartPost`.

## What the script installs

| Item | Path |
| --- | --- |
| Credentials (WPA-PSK hashed, mode 600) | `/etc/wpa_supplicant.conf` |
| systemd unit, enabled at boot | `/etc/systemd/system/wifi-mlan0.service` |
| Resolver config (regular file, replaces the connman symlink) | `/etc/resolv.conf` |

The unit runs `wpa_supplicant -B -Dnl80211 -imlan0` then `udhcpc -b -i mlan0`. Re-running the script with a
different SSID replaces the network. `sh wifi-setup.sh --remove` disables and deletes the unit.

**DNS.** udhcpc's hook (`/etc/udhcpc.d/50default`) hands the WiFi DNS server to systemd-resolved via
`resolvconf` (a symlink to `resolvectl`), but the BSP points `/etc/resolv.conf` at connman's own proxy
(`127.0.0.1`), which only knows about Ethernet. Result: WiFi link up, ping by IP works, every name lookup fails.
The script replaces `/etc/resolv.conf` with a regular file listing resolved's stub `127.0.0.53` first and connman's
proxy second, so both WiFi and Ethernet-only boards resolve. connman keeps writing its own file
(`/etc/resolv-conf.connman`) and does not touch the replacement.

**Flush before unplugging.** The script ends with `sync`. Without it, unplugging a board seconds after setup left a
zero-length unit file on several boards (ext4 delayed allocation + unclean power-off); systemd treats an empty unit
as masked, so WiFi silently never started on the next boot. The script now also refuses to report success if the
unit file is empty, and `--status` prints `unit file: MISSING/EMPTY` if it finds one.

The success output ends with `internet: OK` and `dns: OK`; treat anything else as not done.

## Notes

- Open networks: omit the passphrase (`-SSID 'Guest'` only). WPA3-only (SAE) networks need `key_mgmt=SAE` and
  `ieee80211w=2` added to the network block by hand.
- With both Ethernet and WiFi up the board has two default routes and prefers Ethernet. Unplug the cable to force
  WiFi, or `ip route del default dev eth1`.
- `rfkill: Cannot open RFKILL control device` from wpa_supplicant is harmless (the kernel has no rfkill).
- Exit code 3 with the console showing U-Boot restarting every few seconds after `Source reject request` /
  `Power supply on USB PD` is a **power problem**: the board is browning out. Use a real USB-PD adapter (45 W+, the
  one from the kit) on the POWER port, not a PC port, hub, or 5 V charger, and make sure the debug cable is on the
  DEBUG port. Re-run once the login prompt appears.
- The `hostname` shown in the helper output is the board's identity; every golden clone is `imx95-55ea` until
  `workshop-install.sh` has been run on it.
- Reference: [i.MX Linux User's Guide](https://www.nxp.com/docs/en/user-guide/IMX_LINUX_USERS_GUIDE.pdf).
