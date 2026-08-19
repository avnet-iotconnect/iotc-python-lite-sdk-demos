=====================================================================
 FRDM i.MX 95 GenAI Demo - Quick Start
=====================================================================

1) THE DEMO AUTOSTARTS ON POWER-UP (systemd services genai-app,
   genai-camera, genai-mcp). After plugging in, give it ~90 seconds,
   then paste this health check:

echo "--- demo status ---"
systemctl is-active genai-app   | sed 's/^/cloud app:     /'
systemctl is-active genai-camera| sed 's/^/camera server: /'
systemctl is-active genai-mcp   | sed 's/^/mcp server:    /'
echo "board IP:      $(ip -4 route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')"
echo "board time:    $(date -u) (UTC - if wrong, venue blocks NTP: date -u -s 'YYYY-MM-DD HH:MM:SS'; hwclock --systohc)"

   To restart everything (after a code update or a hang):

systemctl restart genai-app genai-camera genai-mcp

   Logs stay in /opt/demo/{app,camera,mcp}.log as before.

2) WHAT YOU GET

   - Device "MCLiMX95b" goes online in /IOTCONNECT (~15 seconds)
   - Live AI responses page:  https://<board-ip>:8080/responses
   - Live camera stream:      https://<board-ip>:8080/live
     (accept the self-signed certificate warning once in the browser,
      and make sure the dashboard's two Embedded widgets point at the
      board IP shown above)

3) DRIVE IT FROM THE /IOTCONNECT DASHBOARD

   ask-llm <question>      on-device LLM (see set-model / set-backend)
   ask-vlm [question]      describe what the camera sees
   ask-agent <request>     LLM + real board data (time, temp, memory,
                           uptime, IP, USB devices) and IOTCONNECT cloud
                           data (deployment devices, health, telemetry
                           readback via the on-board MCP server)
   voice-start / voice-stop   "Hey NXP" voice assistant
   set-rag on|off          ground answers in the board's documentation
   set-backend cpu|neutron|ara2   CPU, on-chip NPU, or Ara240 module
   set-model <name>        danube / qwen models (bad value lists options)
   set-stt <name>          voice transcriber (moonshine-tiny/base, whisper)

   Full walk-through with timings: see demo-flow.md in the repository
   (nxp-frdm-imx-95/genai-flow-demo/).

4) ONE-TIME: CONNECT THE AGENT TO IOTCONNECT (MCP)

   The agent's cloud tools need the MCP server authenticated once:

iotconnect-cli configure -u <email> -p '<password>' -s <solution-key> --pf aws -e <env>

   (<env> is your IoTConnect environment as shown in the platform URL, e.g. prod)
   The session token refreshes automatically afterwards.

5) STOP THE DEMO - copy and paste:

pkill -f 'python3.*[a]pp\.py'; pkill -f 'camera-serve[r]'; pkill -f 'iotc-mcp-serve[r]'; pkill -f 'eiq_genai_flow'
echo "demo stopped"

=====================================================================
