# Power-Cycle Cheatsheet

Bring-up reference for the SAMA7D65 Curiosity Kit demos (`kws-demo`, `kws-game`, `kws-training`) after the board has been power-cycled. Assumes the board has already been provisioned per the [main quickstart](./README.md), the bundled numpy fix has been applied (see [kws-demo/README.md](./kws-demo/README.md)), and the launcher scripts under `/root/` exist.

> Replace `192.168.1.194`, the AWS account `761303338807`, and the device identities `mcpKWS1` / `blackJack` with whatever your provisioning produced. The values in this file reflect a specific tested instance.

## 0. After power-on (always)

```bash
ssh sama7d65 "ip a | grep 'inet ' | grep -v 127.0.0.1 ; uptime"
```

If SSH cannot reach the board, find the new IP via your router's DHCP table or a serial console (TeraTerm, 115200 8N1, login `root`, then `ifconfig`) and update the `Host sama7d65` block in your `~/.ssh/config`.

If SSH errors with `MAC incorrect` or similar, the dropbear-vs-OpenSSH algorithm workaround is missing from the SSH config. Add `MACs hmac-sha2-256-etm@openssh.com` to the host block.

If the board's IP has changed (DHCP), the host key fingerprint will mismatch on reconnect. Update the `HostName` in `~/.ssh/config` and run `ssh-keygen -R <new-ip>` to drop the stale `known_hosts` entry.

If a launcher fails with `Temporary failure in name resolution`, `/etc/resolv.conf` is broken. The factory image symlinks it to `/run/systemd/resolve/resolv.conf` but systemd-resolved is not running, so the file never appears. Fix:

```bash
ssh sama7d65 "rm -f /etc/resolv.conf ; printf 'nameserver 192.168.1.1\nnameserver 1.1.1.1\nnameserver 8.8.8.8\n' > /etc/resolv.conf"
```

If a launcher fails with `certificate verify failed: certificate is not yet valid`, the board's RTC has lost time (it does not preserve the clock across power cycles, so it boots at the firmware build date — typically ~1 year behind). Set it from your host:

```bash
NOW=$(date -u +"%Y-%m-%d %H:%M:%S") ; ssh sama7d65 "date -u -s '$NOW' ; hwclock -w"
```

## 1. The three demos

The demos share a single USB microphone, so only one can run at a time. Each launcher script kills competing apps before starting, runs the chosen app **in the foreground on the active terminal**, and streams output directly to your screen. Stop with `Ctrl+C`.

| Demo | IOTCONNECT identity | Required template | Start (run from serial console or `ssh`) |
|---|---|---|---|
| KWS demo (yes / no / up / down …) | `mcpKWS1` | `sama7d6Kws` | `/root/run-demo.sh` |
| Voice Blackjack (deal / hit / stand …) | `blackJack` | `sama7d6Bj` | `/root/run-game.sh` |
| Training Studio | `mcpKWS1` | kws-training | `/root/run-training.sh` |

> Flip `mcpKWS1`'s template in /IOTCONNECT before starting the KWS demo (`sama7d6Kws`) or the trainer (kws-training template). `blackJack` stays on `sama7d6Bj` permanently.

## 2. URLs

### Board (only when the relevant demo is running)

| What | URL | Demo |
|---|---|---|
| Voice Blackjack browser game | `http://192.168.1.194:8080` | `kws-game` |
| Training Studio UI | `http://192.168.1.194:8091` | `kws-training` |
| Training health JSON | `http://192.168.1.194:8091/api/state` | `kws-training` |

The basic `kws-demo` has no local web UI; output is /IOTCONNECT telemetry only.

### /IOTCONNECT

- Devices list: /IOTCONNECT portal → **Device → Device**
- `mcpKWS1` device page: Devices → `mcpKWS1` (template flip + Live Data tab)
- `blackJack` device page: Devices → `blackJack`
- Blackjack dashboard (if imported per [kws-game/README.md](./kws-game/README.md#4-import-the-iotconnect-dashboard)): **Dashboards** → "Microchip_Blackjack_Dash"

### AWS (account `761303338807`, region `us-east-1`)

- SageMaker training jobs: `https://us-east-1.console.aws.amazon.com/sagemaker/home?region=us-east-1#/jobs`
- Step Functions conversion state machine `conv-1775928760254`: `https://us-east-1.console.aws.amazon.com/states/home?region=us-east-1#/statemachines`
- Models output bucket: `iotc-761303338807-model-1775928760254`
- Dataset uploads bucket: `iotc-761303338807-telemetry-1775928760254`

## 3. Health checks

The active demo's output already streams in the foreground console where you launched it. From a *second* terminal (SSH or another serial session) you can ask:

```bash
# what's running?
ssh sama7d65 "ps -ef | grep -E 'app.py|game_app|training_app' | grep -v grep"

# trainer state (rich JSON)
ssh sama7d65 "python3 -c 'import urllib.request,json; d=json.loads(urllib.request.urlopen(\"http://127.0.0.1:8091/api/state\").read()); print(json.dumps({\"iotc\":d[\"iotconnect\"][\"ready\"],\"upload\":d[\"upload\"][\"ready\"],\"training\":d[\"training\"][\"ready\"]}, indent=2))'"

# disk + RAM (rootfs is 557 MB, gets tight quickly)
ssh sama7d65 "df -h / ; free -h"
```

## 4. Common operations

| Need | Command |
|---|---|
| Stop the running demo | `Ctrl+C` in the terminal where it's running |
| Switch from game to training | `Ctrl+C` to stop the game, then `/root/run-training.sh` + flip mcpKWS1 template in /IOTCONNECT |
| Switch from training to game | `Ctrl+C` to stop training, then `/root/run-game.sh` |
| Stop everything from another terminal | `ssh sama7d65 "pkill -f app.py ; pkill -f game_app ; pkill -f training_app"` |
| Lower kws-demo / game detection threshold | edit `KWS_DETECTION_THRESHOLD` in `/root/run-demo.sh` or `run-game.sh`, then re-run the launcher |
| Install a different model from S3 onto the board | trainer UI → **Step 3 Install Converted Model** → pick package → **Install** |
| Reboot the board | `reboot` |
| Free disk if rootfs is full | `rm -rf /tmp/* /root/.cache; df -h /` |

## 5. What survives a power cycle (no reinstall needed)

- Board OS, Python 3.12, installed packages: `numpy` (with the `polynomial` + `ma` patch applied), `boto3`, `flask`, `iotconnect-sdk-lite`, `tflite_numpy_interpreter`, `flatbuffers`
- Cert bundles at `/etc/iotconnect/mcpkws1/` and `/etc/iotconnect/blackjack/`
- AWS credentials at `/root/.aws/credentials`
- All three demo source trees: `/root/app.py` + `/root/kws_engine.py` + `/root/tflite/` + `/root/models/` (kws-demo), `/root/kws-game/`, `/root/kws-training/`
- Recorded clip dataset at `/root/kws-training/src/datasets/`
- Currently-installed model in `/opt/demo/models/`
- Helper launcher scripts at `/root/`: `run-demo.sh`, `run-game.sh`, `run-training.sh`, `stop-kws-apps.sh`, `start-kws-training-mcpkws1.sh` — all run their app in the foreground; stop with `Ctrl+C`
- SSH host keys, root password, host-side SSH alias

## 6. What does NOT survive a power cycle

- Any running demo process — re-run the relevant launcher script after every boot
- Anything in `/tmp/` (it is a tmpfs in RAM)
- The board's IP if DHCP rotates the lease
- `/etc/resolv.conf` (broken symlink chain — re-create per Section 0)
- The system clock (RTC is not battery-backed; reset per Section 0 or TLS will fail)

## 7. Related docs

- Initial provisioning: [./README.md](./README.md)
- KWS demo details: [./kws-demo/README.md](./kws-demo/README.md)
- Voice Blackjack details: [./kws-game/README.md](./kws-game/README.md)
- Training Studio architecture and operations: [./kws-training/README.md](./kws-training/README.md), [./kws-training/docs/BOARD_COMMANDS.md](./kws-training/docs/BOARD_COMMANDS.md), [./kws-training/docs/OPERATIONS.md](./kws-training/docs/OPERATIONS.md)
