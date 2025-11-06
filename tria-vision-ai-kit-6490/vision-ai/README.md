# Tria Vision AI-KIT 6490: /IOTCONNECT-Enabled Vision-AI Demo Guide
This guide will help you set up your Tria Vision AI-KIT 6490 to send AI inference and system status telemetry to /IOTCONNECT, 
as well as be controlled by commands from /IOTCONNECT. 

> [!NOTE]
> Currently, this demo supports sending AI inference data for the Pose Detection, 
> Object Detection, and Image Classification demos. The other available demos can be run, but the only telemetry sent for them is the system status data.

## 1. Acquire and Connect Additional Hardware
In addition to the hardware used in the basic demo QuickStart, you will need this hardware to properly enable the Vision-AI demo:

* 1 (or 2) USB or MIPI Camera(s)
  
> [!IMPORTANT]
> Not all USB cameras are compatible with this demo due to different cameras using different default streaming formats. The recommended USB camera used
> by Avnet's engineer is the [Logitech C920x](https://www.amazon.com/Logitech-C920x-Pro-HD-Webcam/dp/B085TFF7M1/ref=sr_1_1?crid=2DCB6QJ10WDGK&dib=eyJ2IjoiMSJ9.9dhz6_AJ2VGaHtlxmHe75fS5Aq_5Xk1UwuQ4mWyJRql90THv_Se4qTFWSqCyRX_MEI5kpVF15WwCJgdRL4kDiNgPkBOMduYm8gF4NxQtWONUECYNc2_Xvja8vpAMuD7hpEGL25cNp2YlsbWbVFdidLTmBvhcyC86eEOFquUGk-iK4iDQis3GCwnaFtk-UOi2WD0I3XYJaHSn6cJHbWgVLSczE_6u9AuvHAiNfZviRII.Cd5uQLrB0R28ezkBCMQBFXfH1h-TAID_PHayHdtU3w4&dib_tag=se&keywords=logitech%2Bc920&qid=1762414911&sprefix=logitech%2Bc920%2Caps%2C132&sr=8-1&th=1).

> [!NOTE]
> The Vision AI-KIT 6490 is capable of running 2 simultaneous Vision-AI demos, which would require 2 cameras to be connected. To run a single demo, only 1 camera is needed.
> For simplicity, the /IOTCONNECT dashboard provided in this guide is only for a single-camera setup but it can be modified to support a dual-camera (dual-demo) setup.

* 1 Monitor with an HDMI input
* 1 HDMI cable
* 1 **Active** mini-DP to HDMI adapter

> [!IMPORTANT]
> The mini-DP to HDMI adapter must be **active** so to avoid purchasing the wrong product it is recommended to use the adapter used and tested by Avnet's engineer available [here](https://www.amazon.com/Cable-Matters-DisplayPort-Supporting-Technology/dp/B00PJ3LSIG/ref=sr_1_1?crid=XR4HA3U2IVD0&dib=eyJ2IjoiMSJ9.7o239haE8CcYdAqsOPF7Se6OXe8Sz47i-Az7Mq9_PvLySbMg4xxB8QbnT7rNODDTxSh882r-DD24OPLilxONY3rqmtq2d-y9-PdgAE7xHVKKFR7sSypCPC5w6yW8QYkxKJag31Qy-DlnbIz1F9XIBGWrG6Ric9NSsSSTfHpZG58gk_bvzo6qGpsQa11HI9C3rp4MSgjK6X5zBcp_98AzK_elv_1tTuomClMsDK_tZuw.c21P4pWnM5M33qDFmO5u0CjFbJWeyxQZ93-Fv3nExKw&dib_tag=se&keywords=cable+matters+mini+dp+to+hdmi&qid=1762415607&sprefix=%2Caps%2C84&sr=8-1).

* (Optional) 1 USB Mouse

> [!NOTE]
> A mouse allows you to select the active demos locally on your monitor instead of via /IOTCONNECT commands if you wish to have that capability.

Connect your camera(s) to their associated ports on the board, the mini-DP to HDMI adapter to an HDMI cable to your monitor, and your USB mouse to an open USB port.

After connecting these, unplug the power to your board and then reconnect it and power up the board again to ensure the USB devices get detected properly.

After the board powers up successfully, a pink screen with the Tria logo should appear on your monitor.

> [!NOTE]
> It can take a minute or two for a USB mouse to be detected and usable by the board after booting up. Every few seconds move your mouse around until you see a cursor appear and move
> on the screen.

## 2. Download Demo Zip Archive
Download the zip archive containing the necessary demo and template files [here](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/raw/refs/heads/main/tria-vision-ai-kit-6490/vision-ai/QCS6490-Vision-AI-Demo.zip).

Unzip the archive and inside is a folder called `QCS6490-Vision-AI-Demo` which contains the Vision-AI demo files as well as these two /IOTCONNECT template files:

* `VAI6490-template.json`
* `vision-ai-kit-6490-dashboard-template.json`

The two template files can be copied out to a different local location on your PC and then deleted from the folder.

> [!NOTE]
> Leaving the template files in the folder to be copied onto the device is **harmless** but it is recommended they are moved for organizational purposes.

## 3. Import Device Template into /IOTCONNECT

Follow these steps to import the `VAI6490-template.json` template into /IOTCONNECT so your Vision AI-KIT 6490 can be configured to send commands and receive the correct telemetry:

1. In /IOTCONNECT, go to the navy-blue vertical toolbar on the left side of your screen and hover over the “processor” icon.
2. In the resulting drop-down menu, click on “Device”.
3. Now in the Device page, locate the navy blue horizontal toolbar along the bottom of the screen and click on “Templates”.
4. Now in the Templates page, in the top-right of your screen click on the navy blue button labeled “Create Template”.
5. Now in the template creation page, in the top-right of your screen click on the navy blue button labeled “Import”.
6. In the resulting pop-up click “Browse” to search for and upload `VAI6490-template.json`.
7. Click the “Save” button in the pop-up window to create the template.

## 4. Set Up Device
Now that the device template is imported, you will be able to create your device so that it is configured for the Vision-AI demo. Follow these steps:

1. In /IOTCONNECT, go to the navy-blue vertical toolbar on the left side of your screen and hover over the “processor” icon.
2. In the resulting drop-down menu, click on “Device”.
3. Now in the Device page, in the top-right of your screen click on the navy blue button labeled “Create Device”.
4. Fill in the “Unique ID” and “Device Name” fields with the desired name for your device (both fields should be identical).
5. The “Entity” field is only used for online organizational purposes (doesn’t affect connectivity or performance), so it doesn’t matter which you choose.
6. In the “Template” dropdown, select “VAI6490” (if there is a long list of templates, you can just type “VAI” into the bar and it should come up to be selected).
7. After selecting the template, a “Device Certificate” option will appear. Change it to “Use my certificate”. Leave this page where it is for now.
8. Log into the console of the board using your preferred method.
>[!TIP]
>Instructions for UART, USB, SSH, and local terminal explained starting on page 30 of
>[Tria's Startup Guide](https://avnet.com/wcm/connect/137a97f1-eb6e-48ba-89a4-40b024558593/Vision+AI-KIT+6490+Startup+Guide+v1.3.pdf?MOD=AJPERES&attachment=true&id=1761931434976) for the board.

9. Execute the command `ip a` to see the network information for your board and note its ethernet IP address to be used for file transfers in a later step.
10. Execute this command to install the /IOTCONNECT Python Lite SDK on your board:
    
```
python3 -m pip install iotconnect-sdk-lite
```

11. Navigate to the directory `/var/rootdirs/opt/QCS6490-Vision-AI-Demo/iotc_config`.

12. Then run this command to execute the quickstart script:

```
bash ./quickstart.sh
```

13. After the script has started, it will instruct you to start the device-creation process (which you have already done) and then to press ENTER to generate a certificate.
Press ENTER and the certificate will be printed and then you can copy that certificate (including the BEGIN and END lines) and paste it into “Certificate Text” box in the
/IOTCONNECT device creation page where you left off.
14. As instructed by the script, click the “Save & View” button to be taken to the new device page and then in the top-right section of the new device page, to the right of
the red “DISCONNECTED” status, you will see an icon that is a white paper with a green processor and a black cog on it. Click on that icon to download the device configuration JSON file.
15. Open the downloaded device configuration JSON, and copy its entirety and paste it into the prompt in the quickstart script and then press ENTER.
> [!NOTE]
> The quickstart script will automatically download a quickstart python app but it can be ignored for this demo.
16. Leave the `iotc_config` directory to get back to the `/var/rootdirs/opt/QCS6490-Vision-AI-Demo` where you will execute a command to start the demo after setting up the dashboard.

## 5. Set Up Vision-AI Dashboard in /IOTCONNECT
Now that your device is configured properly for the Vision-AI demo, it is time to set up a dashboard in your /IOTCONNECT account to view some of the AI inference and system status data, as 
well as send commands to your device to start and stop demos on different AI models remotely. Follow these steps:

1. In /IOTCONNECT, along the top of the screen you should see 3 dashboard-related buttons. Click on “Create Dashboard”.
2. At the first radio-button choice, select “Import Dashboard”.
3. Click “Browse” to search for and upload `vision-ai-kit-6490-dashboard-template.json`
4. In the resulting window, under “Template” select “VAI6490”.
5. Under “Device” select the device that this dashboard is going to be connected to
> [!NOTE]
> The list of options will only include devices that have the VAI6490 template so you won’t have to wade through a long list.

6. Name the dashboard to your liking.
7. Leave all other options as-is and click “Save”.
8. You will be taken into the “editing” version of the dashboard, so in the top-right of the screen click the “Save” button again to get to the “presenting” version (editing version sometimes doesn’t display data correctly).
> [!TIP]
> Depending on your monitor size, zoom the browser in/out to your desired viewing level.


## 6. Run and Control the Vision-AI Demo

Back in the directory `/var/rootdirs/opt/QCS6490-Vision-AI-Demo` on your board, and run this command to start the demo:

```
bash ./launch_visionai_with_env.sh
```

You will see the local demo dashboard come up on your monitor, and a steady stream of output from the console including periodic system status telemetry being sent to /IOTCONNECT.

> [!TIP]
> If directly after launching the demo you see in the console output that no cameras were detected, try power cycling the board and running it again. This usually only happens
> if the board is not power cycled after connecting the cameras in the first place.

To **locally start** a demo on an AI model, use your mouse to click on the dropdown menu for an active camera on your local monitor's dashboard and select the demo you wish to start.

To **locally stop** a demo, click on "None" in the same dropdown list.

To **start** a demo from the /IOTCONNECT dashboard, use the "Device Command" widget (top-right corner of dashboard from /IOTCONNECT template) to select the "Start Demo" command and then enter
these 2 parameters:

1. Camera Number
     * "cam0" (always available)
     * "cam1" (only available if 2 cameras connected)

2. Demo Number
     * "0" (None/Idle)
     * "1" (Camera feed without AI models)
     * "2" (Pose Detection)
     * "3" (Segmentation)
     * "4" (Classification)
     * "5" (Object Detection)
     * "6" (Depth Segmentation)

For example if you wanted to start a Pose Detection demo on camera 0, you would enter `cam0 2` as your parameters (no quotation marks).

To **stop** a demo from the /IOTCONNECT dashboard, again use the "Device Command" widget (top-right corner of dashboard from /IOTCONNECT template) to select the "Stop Demo" command and then enter
this 1 parameter:

1. Camera Number
     * "cam0" (always available)
     * "cam1" (only available if 2 cameras connected)
  
For example if you wanted to stop the active demo on camera 1, you would enter `cam1` as your parameters (no quotation marks).

> [!TIP]
> You **do not need to stop an active demo model to switch to a different demo on the same camera.** If you send a proper start command to the board for a camera that is already
> running a demo, it will automatically shift to the new requested demo.

To properly shut the entire application down, you can either type `ctrl+C` in the console window where the demo was launched or you can use your mouse to click on the "Exit" button 
on the local monitor.
