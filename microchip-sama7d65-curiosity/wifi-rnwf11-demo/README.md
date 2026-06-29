# WiFi Connectivity Demo (EV12H55A / RNWF11)

Upgrades the /IOTCONNECT Starter Demo on the Microchip SAMA7D65-Curiosity Kit to connect to /IOTCONNECT over the **EV12H55A WiFi Add-on Board** (RNWF11) instead of the board's built-in Ethernet.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the Microchip SAMA7D65-Curiosity Kit](../README.md) before proceeding. You must have a working Ethernet-connected demo (with `iotcDeviceConfig.json`, `device-cert.pem`, and `device-pkey.pem` on the board at `/opt/demo/`) before starting this expansion.

## 1. Introduction

The **Microchip EV12H55A** is a mikroBUS™ "Click" add-on board built around the **RNWF11** WiFi module. It exposes WiFi connectivity over a UART using ASCII AT commands — it does **not** present itself to Linux as a standard network interface (there is no `wlan0`).

This demo adds a small transport bridge (`rnwf11_transport.py`) that intercepts the IoTConnect SDK's outgoing MQTT connection and redirects it through the module's raw TCP socket AT commands. TLS, MQTT, and all credential handling continue to run entirely in Python on the Linux side, exactly as in the standard Ethernet quickstart — the module only ever carries the encrypted bytes.

**No modified or custom SDK is needed.** The standard `iotconnect-sdk-lite` package is used without modification.

## 2. Additional Hardware Required

* **Microchip EV12H55A** (RNWF11 "UART to Cloud" WiFi Add-on Board) — [Purchase](https://www.microchipdirect.com/dev-tools/EV12H55A?allDevTools=true)

> [!NOTE]
> An Ethernet cable is still needed for initial board setup and to resolve the /IOTCONNECT broker hostname via DNS on first connect. The app uses `socket.gethostbyname()` over Ethernet once, then hands only the raw IP address to the WiFi module.

## 3. Attach the WiFi Module

### Step 1: Plug into mikroBUS1

The SAMA7D65-Curiosity Kit has two mikroBUS sockets (**J25 / mikroBUS1** and **J26 / mikroBUS2**). **Use mikroBUS1** (the socket nearest the Ethernet connectors) — mikroBUS2 is wired to a different UART and will not work with the setup in this guide.

Align the module's pins with the mikroBUS1 socket as shown below (green check) and press down firmly until fully seated.

<img src="./media/wifi-module.png" width="400" />

> [!NOTE]
> It is easy for one row of pins to sit slightly proud if the module goes in at a slight angle. Verify all 8 pins on both rows are fully inserted before powering on.

### Step 2: Set the module's power-source jumper

The WiFi module has a 3-pin power-selection header labeled **J5** (on the module itself) that selects whether it draws 3.3V from USB or from the mikroBUS connector. Since we're powering it from the mikroBUS connector, move the jumper cap to the position circled below.

<img src="./media/wifi-jumper.png" width="300" />

> [!WARNING]
> Modules typically ship with the jumper in the *other* position (set up for USB power), which will **not** work for this setup — WiFi connectivity will silently fail with no obvious error. Check the jumper position against the photo above before continuing, even if you haven't touched it.

## 4. Enable the WiFi Module UART

The mikroBUS1 RX/TX pins are not enabled as a UART by default — the board's device tree leaves them unconfigured out of the box. The [`wifi-module`](./wifi-module) folder contains a device tree overlay and a setup script that enables them permanently.

### Step 1: Copy the `wifi-module` folder to the board

From your PC (replace `<board-ip>` with your board's IP address):

```bash
scp -r wifi-module root@<board-ip>:/root/wifi-module
```

### Step 2: Run the setup script on the board

```bash
ssh root@<board-ip>
cd /root/wifi-module
python3 apply_wifi_overlay.py
```

This backs up the board's existing boot environment, patches it to load the WiFi UART overlay on every boot, and copies the overlay file onto the boot partition.

### Step 3: Power-cycle the board

Unplug and replug the USB-C power cable (a soft reboot is not sufficient). After the board boots back up, confirm the UART is available:

```bash
ls /dev/ttyS1
```

If `/dev/ttyS1` exists, the WiFi module's UART is enabled and ready.

> [!TIP]
> If you ever need to undo this change, the original boot environment was backed up to `/uboot.env.bak` on the boot partition before it was modified.

### Step 4: Verify WiFi connectivity (optional but recommended)

Run this snippet on the board to confirm the module can join your network before deploying the full demo:

```python
import serial, time

ser = serial.Serial('/dev/ttyS1', 230400, timeout=1)

def send(cmd, wait=1):
    ser.write((cmd + '\r\n').encode())
    time.sleep(wait)
    print(cmd, '->', ser.read(2000).decode(errors='replace'))

send('AT+GMM')                          # confirm the module responds
send('AT+WSCN=0', wait=5)               # scan -- note the security type next to your SSID
send('AT+WSTAC=1,"YOUR_SSID"')
send('AT+WSTAC=2,YOUR_SECURITY_TYPE')   # from the AT+WSCN output
send('AT+WSTAC=3,"YOUR_PASSWORD"')
send('AT+WSTAC=4,0')
send('AT+WSTA=1', wait=10)              # look for a +WSTAAIP: line with an IP address
```

A successful connection prints a `+WSTAAIP:` line with an IP address from your network.

## 5. Deploy and Run

### Install the demo package

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/microchip-sama7d65-curiosity/wifi-rnwf11-demo/packages/wifi-rnwf11-package.tar.gz
tar -xzf wifi-rnwf11-package.tar.gz --overwrite
bash ./install.sh
```

### Create your WiFi credentials file

The demo reads WiFi credentials from `wifi_config.json` (which is never committed to this repo). Create it from the included template:

```bash
cp wifi_config.json.example wifi_config.json
nano wifi_config.json
```

Fill in your network's SSID and password:

```json
{
  "ssid": "YOUR_SSID",
  "password": "YOUR_PASSWORD"
}
```

> [!NOTE]
> You do not need to look up your network's security type — the app scans for it automatically on first connect.

### Run the demo

```bash
cd /opt/demo
python3 app.py
```

On startup the app joins your WiFi network, opens a raw TCP socket to the /IOTCONNECT MQTT broker through the module, and then runs TLS and MQTT entirely in Python. View the random-integer telemetry under the **Live Data** tab for your device on /IOTCONNECT.

> [!NOTE]
> Always run from the `/opt/demo` directory so the app can find `iotcDeviceConfig.json`, `device-cert.pem`, `device-pkey.pem`, and `wifi_config.json`.

## 6. How It Works

The RNWF11 module only exposes AT commands — there is no kernel driver or Linux network interface. This demo bridges the gap with `rnwf11_transport.py`:

1. The SDK's `Client.__init__` makes a plain HTTPS call over the board's **Ethernet** to fetch the MQTT broker hostname from the /IOTCONNECT REST API.
2. The app resolves that hostname to an IP address (also over Ethernet/DNS) and connects a raw TCP socket through the RNWF11's `AT+SOCKBR` command.
3. A background thread (`Rnwf11MqttTransport`) pumps raw bytes between one end of a `socket.socketpair()` and the RNWF11 socket using `AT+SOCKWR` / `AT+SOCKRD`.
4. The other end of the `socketpair()` is handed to paho-mqtt via a single private-method override (`_create_socket_connection`). From paho's perspective it has a normal socket — it runs TLS and MQTT exactly as it would over Ethernet.

The module only ever sees opaque, encrypted TLS bytes. All credential and certificate handling stays in Python on the Linux side.

## 7. Resources

* [Purchase the Microchip EV12H55A (RNWF11 WiFi Add-on Board)](https://www.microchipdirect.com/dev-tools/EV12H55A?allDevTools=true)
* [RNWF11 Product Page](https://www.microchip.com/en-us/product/rnwf11pc)
* [/IOTCONNECT Quickstart for SAMA7D65](../README.md)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
