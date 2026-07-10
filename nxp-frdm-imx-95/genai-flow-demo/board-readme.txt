=====================================================================
 FRDM i.MX 95 GenAI Demo - Quick Start
=====================================================================

1) START THE DEMO - copy and paste this whole block:

pkill -f 'python3.*[a]pp\.py'; pkill -f 'camera-serve[r]'; pkill -f 'iotc-mcp-serve[r]'; sleep 2
cd /opt/demo
setsid nohup python3 -u app.py > app.log 2>&1 < /dev/null &
setsid nohup python3 -u camera-server.py > camera.log 2>&1 < /dev/null &
setsid nohup iotc-mcp-server > mcp.log 2>&1 < /dev/null &
sleep 10
echo "--- demo status ---"
pgrep -f 'python3.*app\.py' > /dev/null && echo "cloud app:     RUNNING" || echo "cloud app:     FAILED (see /opt/demo/app.log)"
pgrep -f 'camera-server'    > /dev/null && echo "camera server: RUNNING" || echo "camera server: FAILED (see /opt/demo/camera.log)"
pgrep -f 'iotc-mcp-server'  > /dev/null && echo "mcp server:    RUNNING" || echo "mcp server:    FAILED (see /opt/demo/mcp.log)"
echo "board IP:      $(ip -4 -br addr show eth0 | awk '{print $3}' | cut -d/ -f1)"

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
   set-backend cpu|neutron    CPU vs on-chip NPU
   set-model <name>        danube / qwen models (bad value lists options)
   set-stt <name>          voice transcriber (moonshine-tiny/base, whisper)

   Full walk-through with timings: see demo-flow.md in the repository
   (nxp-frdm-imx-95/genai-flow-demo/).

4) ONE-TIME: CONNECT THE AGENT TO IOTCONNECT (MCP)

   The agent's cloud tools need the MCP server authenticated once:

iotconnect-cli configure -u <email> -p '<password>' -s <solution-key> --pf aws -e poc

   The session token refreshes automatically afterwards.

5) STOP THE DEMO - copy and paste:

pkill -f 'python3.*[a]pp\.py'; pkill -f 'camera-serve[r]'; pkill -f 'iotc-mcp-serve[r]'; pkill -f 'eiq_genai_flow'
echo "demo stopped"

=====================================================================
