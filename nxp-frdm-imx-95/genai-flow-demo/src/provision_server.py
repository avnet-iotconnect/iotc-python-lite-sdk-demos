#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# -----------------------------------------------------------------------------
# Workshop provisioning server - "claim this board" page.
#
# Runs on the board (port 8088, plain HTTP on the workshop LAN). An attendee
# who signed up on the onboarding portal browses to this board's URL (printed
# on its card, e.g. http://imx95-a1b2.local:8088), drops their board-kit .zip
# on the page, and the board installs the identity, (re)starts the demo, and
# reports live when it is connected to /IOTCONNECT as THEIR device.
#
# Multi-board rooms: each board has a unique mDNS hostname (set by
# workshop-install.sh from the MAC address). A board that is already claimed
# says so and requires an explicit re-claim confirmation, so nobody grabs a
# neighbor's board by accident.
# -----------------------------------------------------------------------------
import io
import json
import os
import re
import shutil
import subprocess
import time
import zipfile
import http.server

PORT = int(os.environ.get("PROVISION_PORT", "8088"))
DEMO_DIR = os.environ.get("DEMO_DIR", "/opt/demo")
STATE = "/tmp/genai-state.json"
APP_LOG = os.path.join(DEMO_DIR, "app.log")
KIT_FILES = ("iotcDeviceConfig.json", "device-cert.pem", "device-pkey.pem")


def board_name():
    try:
        return open("/etc/hostname").read().strip()
    except OSError:
        return "imx95"


def current_identity():
    try:
        cfg = json.load(open(os.path.join(DEMO_DIR, "iotcDeviceConfig.json")))
        return cfg.get("uid")
    except Exception:
        return None


def demo_connected():
    """Freshly-updated state file = the demo app is alive and publishing."""
    try:
        return (time.time() - os.path.getmtime(STATE)) < 30
    except OSError:
        return False


def restart_demo():
    r = subprocess.run(["systemctl", "restart", "genai-app"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode == 0:
        return "systemd"
    subprocess.run(["pkill", "-f", "python3 -u? ?app.py"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    subprocess.Popen(["nohup", "python3", "-u", "app.py"], cwd=DEMO_DIR,
                     stdout=open(APP_LOG, "w"), stderr=subprocess.STDOUT)
    return "nohup"


def validate_kit(data):
    """Returns (files dict, uid) or raises ValueError."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("That file is not a .zip - upload the board kit downloaded from the portal.")
    names = z.namelist()
    files = {}
    for want in KIT_FILES:
        match = next((n for n in names if n.endswith(want)), None)
        if not match:
            raise ValueError("Kit is missing %s - upload the unmodified board-kit zip." % want)
        files[want] = z.read(match)
    try:
        cfg = json.loads(files["iotcDeviceConfig.json"])
        uid = cfg["uid"]
    except (ValueError, KeyError):
        raise ValueError("iotcDeviceConfig.json in the kit is not valid.")
    if b"BEGIN CERTIFICATE" not in files["device-cert.pem"]:
        raise ValueError("device-cert.pem does not look like a certificate.")
    if b"PRIVATE KEY" not in files["device-pkey.pem"]:
        raise ValueError("device-pkey.pem does not look like a private key.")
    return files, uid


PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claim board %(name)s</title>
<style>
 :root{--bg:#0e1116;--card:#161b22;--line:#2a3441;--fg:#e6edf3;--dim:#8b98a5;--acc:#33b5e5;--ok:#3fb950;--err:#f85149;--warn:#d29922}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:560px;margin:0 auto;padding:34px 20px;text-align:center}
 h1{font-size:1.5rem}h1 span{color:var(--acc)}
 .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:24px;margin:16px 0}
 .drop{border:2px dashed var(--line);border-radius:12px;padding:36px 16px;cursor:pointer;transition:.15s}
 .drop.hover{border-color:var(--acc);background:#0d2030}
 .dim{color:var(--dim)}.ok{color:var(--ok)}.err{color:var(--err)}.warn{color:var(--warn)}
 .big{font-size:1.2rem;font-weight:700}
 .spin{display:inline-block;width:16px;height:16px;border:2px solid var(--acc);border-top-color:transparent;border-radius:50%%;animation:r .9s linear infinite;vertical-align:-3px;margin-right:8px}
 @keyframes r{to{transform:rotate(360deg)}}
 a{color:var(--acc)} label{font-size:.85rem}
 input[type=checkbox]{accent-color:var(--warn)}
</style></head><body><div class="wrap">
<h1>Board <span>%(name)s</span></h1>
<p class="dim">FRDM i.MX 95 &middot; eIQ GenAI workshop</p>
<div class="card" id="claimed" style="display:%(claimed_disp)s">
 <div class="big warn">This board is already claimed</div>
 <p>Device <b id="curuid">%(uid)s</b> is installed here. If this is <em>not</em> your board,
 check the card next to it for the right address.</p>
 <label><input type="checkbox" id="confirm"> I'm sure this is my board - replace its identity</label>
</div>
<div class="card">
 <div class="drop" id="drop">
  <div class="big">Drop your board-kit .zip here</div>
  <div class="dim">or click to choose the file<br>(downloaded from the signup portal)</div>
  <input type="file" id="file" accept=".zip" style="display:none">
 </div>
 <div id="status" style="margin-top:14px"></div>
</div>
<p class="dim" style="font-size:.8rem">Your kit stays on this board only. After claiming, manage your device at
<a href="https://awspoc.iotconnect.io" target="_blank">awspoc.iotconnect.io</a></p>
<script>
const $=id=>document.getElementById(id);
const claimed = %(claimed_js)s;
function st(h){$("status").innerHTML=h}
async function send(f){
 if(claimed && !$("confirm").checked){st('<span class="err">This board is already claimed - tick the confirmation box above to replace it.</span>');return}
 st('<span class="spin"></span>Installing your identity…');
 try{
  const r = await fetch("api/claim",{method:"POST",headers:{"Content-Type":"application/zip"},body:await f.arrayBuffer()});
  const j = await r.json();
  if(!r.ok) throw new Error(j.error||("HTTP "+r.status));
  st('<span class="spin"></span>Identity installed (device <b>'+j.uid+'</b>). Waiting for /IOTCONNECT connection…');
  for(let i=0;i<20;i++){
   await new Promise(x=>setTimeout(x,3000));
   const s = await (await fetch("api/status")).json();
   if(s.connected){st('<div class="big ok">&#10003; Connected as '+j.uid+'</div><div>Open <a href="https://awspoc.iotconnect.io" target="_blank">your dashboard</a> - this board is now yours.</div>');return}
  }
  st('<span class="warn">Identity installed, but no connection after 60 s - ask the workshop host to check the network.</span>');
 }catch(e){st('<span class="err">'+e.message+'</span>')}
}
$("drop").onclick=()=>$("file").click();
$("file").onchange=e=>{if(e.target.files[0])send(e.target.files[0])};
["dragover","dragleave","drop"].forEach(ev=>$("drop").addEventListener(ev,e=>{
 e.preventDefault();$("drop").classList.toggle("hover",ev==="dragover");
 if(ev==="drop"&&e.dataTransfer.files[0])send(e.dataTransfer.files[0]);
}));
</script>
</div></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            uid = current_identity()
            page = PAGE % {"name": board_name(), "uid": uid or "",
                           "claimed_disp": "" if uid else "none",
                           "claimed_js": "true" if uid else "false"}
            self._send(200, page, "text/html; charset=utf-8")
        elif self.path == "/api/status":
            uid = current_identity()
            self._send(200, json.dumps({"claimed": bool(uid), "uid": uid,
                                        "connected": bool(uid) and demo_connected()}))
        else:
            self._send(404, '{"error":"not found"}')

    def do_POST(self):
        if self.path != "/api/claim":
            self._send(404, '{"error":"not found"}')
            return
        n = int(self.headers.get("Content-Length", "0"))
        if n <= 0 or n > 5 * 1024 * 1024:
            self._send(400, '{"error":"empty or oversized upload"}')
            return
        data = self.rfile.read(n)
        try:
            files, uid = validate_kit(data)
        except ValueError as e:
            self._send(400, json.dumps({"error": str(e)}))
            return
        old = current_identity()
        if old and old != uid:
            backup = os.path.join(DEMO_DIR, "identity-backup-%d" % int(time.time()))
            os.makedirs(backup, exist_ok=True)
            for f in KIT_FILES:
                p = os.path.join(DEMO_DIR, f)
                if os.path.exists(p):
                    shutil.copy2(p, backup)
        for f, content in files.items():
            with open(os.path.join(DEMO_DIR, f), "wb") as fh:
                fh.write(content)
        how = restart_demo()
        print("claimed by %s (was %s) - demo restarted via %s" % (uid, old, how), flush=True)
        self._send(200, json.dumps({"uid": uid, "restarted": how}))


def main():
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("provisioning server on http://0.0.0.0:%d (board %s)" % (PORT, board_name()), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
