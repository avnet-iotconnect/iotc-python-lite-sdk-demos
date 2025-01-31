
# WiFi Setup Guide for NXP FRDM-i.MX93 with Yocto

This guide explains how to set up and connect WiFi on the NXP FRDM-i.MX93 running Yocto. It includes instructions for ensuring connections persist after reboots.

---

## Requirements

1. NXP FRDM-i.MX93 development board running Yocto.
2. WiFi network credentials (SSID and passphrase).
3. Bluetooth device for pairing.
4. Access to the board via serial terminal or SSH.

---

## WiFi 

### Step 1: Load WiFi Module

Run the following command to load the WiFi module:

```bash
modprobe moal mod_para=/lib/firmware/nxp/wifi_mod_para.conf
```

---

### Step 2 (Optional): Create a Systemd Service File to Bring Up WiFi Devices

1. Create a new service file for the WiFi setup:

   ```bash
   nano /etc/systemd/system/wifi-setup.service
   ```

2. Add the following content to the file:

   ```ini
   [Unit]
   Description=WiFi Setup
   After=network.target

   [Service]
   Type=oneshot
   ExecStart=/sbin/modprobe moal mod_para=/lib/firmware/nxp/wifi_mod_para.conf
   RemainAfterExit=yes

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable the service to start at boot:

   ```bash
   systemctl daemon-reload
   systemctl enable wifi-setup.service
   systemctl start wifi-setup.service
   ```

---

### Step 3: Connecting to Wi-Fi Using `connmanctl`

#### 1. Enable Wi-Fi

Open the ConnMan command-line tool:

```bash
connmanctl
```

Enable Wi-Fi if it is not already enabled:

```bash
enable wifi
```

If Wi-Fi is already enabled, you will see:

```
wifi is already enabled
```

---

#### 2. Scan for Wi-Fi Networks

Run the following command to scan for available networks:

```bash
scan wifi
```

Wait for the scan to complete. You will see:

```
Scan completed for wifi
```

---

#### 3. List Available Wi-Fi Networks

List the detected Wi-Fi networks:

```bash
services
```

This will display a list of available networks, such as:

```
wifi_xxxx_xxxxxxxxxxxx_managed_psk
```

---

#### 4. Enable the ConnMan Agent

Enable the agent to handle input requests for authentication:

```bash
agent on
```

You will see:

```
Agent registered
```

---

#### 5. Connect to a Wi-Fi Network

Use the following command to connect to your chosen network. Replace `wifi_xxxx_xxxxxxxxxxxx_managed_psk` with the identifier of your target network:

```bash
connect wifi_xxxx_xxxxxxxxxxxx_managed_psk
```

If the network requires a passphrase, you will be prompted with a message like this:

```
Agent RequestInput wifi_xxxx_xxxxxxxxxxxx_managed_psk
  Passphrase = [ Type=psk, Requirement=mandatory, Alternates=[ WPS ] ]
Passphrase?
```

Enter the passphrase for the network (e.g., `yourpassword`) and press **Enter**.

Once connected, you will see:

```
Connected wifi_xxxx_xxxxxxxxxxxx_managed_psk
```

---

#### 6. Exit ConnMan

Type the following to exit the `connmanctl` interface:

```bash
quit
```

---

### Step 4: Verify the Connection

#### 1. Check the Connection Details

You can verify the connection settings by inspecting the configuration file for your network:

```bash
cat /var/lib/connman/wifi_xxxx_xxxxxxxxxxxx_managed_psk/settings
```

Example output:

```
[wifi_xxxx_xxxxxxxxxxxx_managed_psk]
Name=YourNetworkSSID
SSID=xxxxxxxxxxxxxxxxxxxx
Frequency=2447
Favorite=true
AutoConnect=true
Modified=2025-01-28T16:56:07Z
Passphrase=yourpassword
IPv4.method=dhcp
IPv4.DHCP.LastAddress=192.168.68.65
IPv6.method=auto
IPv6.privacy=disabled
```

#### 2. Test the Internet Connection

Ping an external server to confirm internet access:

```bash
ping google.com
```

You should see responses like this:

```
PING google.com (142.250.115.102) 56(84) bytes of data.
64 bytes from rq-in-f102.1e100.net (142.250.115.102): icmp_seq=1 ttl=57 time=11.0 ms
64 bytes from rq-in-f102.1e100.net (142.250.115.102): icmp_seq=2 ttl=57 time=27.7 ms
```

Press **`Ctrl + C`** to stop the ping command.

---

### Step 5: Make Wi-Fi Persistent Across Reboots

1. Ensure that the Wi-Fi module is loaded during boot using the `wifi-setup.service` file created earlier.
2. Confirm that the network configuration file exists in the `/var/lib/connman/` directory. Verify that the `Favorite` and `AutoConnect` fields are set to `true` in the network’s settings file.


---

## Additional Resources

For more detailed information, refer to the [i.MX Linux User's Guide](https://www.nxp.com/docs/en/user-guide/IMX_LINUX_USERS_GUIDE.pdf).
