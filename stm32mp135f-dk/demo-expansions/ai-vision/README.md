## AI Vision Expansion Demo
The STM32MP135F-DK supports the X-LINUX-AI expansion package, and a basic IoTConnect connect demo has been created to showcase this capability. The demo detects objects held/placed in front of the camera and periodcially sends information (object names, confidence percentage, and confidence rankings) regarding the detected objects to IoTConnect.

## Step 1: Acquire Necessary Files
* Download the vision-ai-expansion.zip folder in this directory and extract it to a known location

* Within the unzipped folder, locate the AIMP1_template.JSON file and use it as the template when creating your device in IoTConnect

## Step 2: Configure Board for AI Vision

* Execute these commands to install and set up the X-LINUX-AI packages:
```
sudo apt-get install x-linux-ai-tool -y
sudo apt-get update
x-linux-ai -i packagegroup-x-linux-ai-demo
systemctl restart weston-graphical-session.service
```

* Using SCP (or a Windows equivalent utility like WinSCP), copy these 2 files from the expansion folder into the "/usr/local/x-linux-ai/object-detection' directory:
```
launch-vision-program.sh
iotc-vision-program.py
```

* Using the same method, copy these 3 files from the expansion folder into the "/home/weston" directory:
```
MP135-vision-demo.py
ack.txt
objects-detected.txt
```

* Next, make the launching script executable with this command:

```sudo chmod +x /usr/local/x-linux-ai/object-detection/launch-vision-program.sh```

## Step 3: Physically Set Up Demo Equipment
* Using adhesive, zip-ties, or some other type of binding utility, secure your USB camera in a position to be looking at your designated detection area.

>[!TIP]
>To maintain a consistent and controlled background, it is recommended to position the camera above a tabletop secured to a boom arm (such as [this](https://www.amazon.com/dp/B0BV2SBWVD?ref=cm_sw_r_apan_dp_XVFHFPZQA55SFZY5S988&ref_=cm_sw_r_apan_dp_XVFHFPZQA55SFZY5S988&social_share=cm_sw_r_apan_dp_XVFHFPZQA55SFZY5S988&peakEvent=1&starsLeft=1&skipTwisterOG=1&th=1)), looking down at objects on the table.

>[!IMPORTANT]
>The AI Vision Demo requires a USB UVC-Compliant Camera (such as [this](https://www.amazon.com/ALPCAM-Distortion-Compliant-Embedded-Industrial/dp/B0B1WTV1KB/ref=sr_1_40?crid=1Y64R6N37I2DW&dib=eyJ2IjoiMSJ9.09vlNQuRgZXBCOJltq5NAHjwkF3xrkD_IO8iIPnTgmM656JhZdERupdaYL29K-WbqLGgdkCchkhjMGFCFpy7D4Ng5LfWuSsYX1jMf8HFDXXsuqE96PFQrpwZszNnYEAkgDOKVRYky4lgiGU4S8NZZEcnmANwxdgvAOnkQCDQWIYxf2Tau45lZyN0ZjY5Otk6.TwrVuCH8OFqthDivTQqbOEPSUYAmvtH5LiE27DyAm7A&dib_tag=se&keywords=usb%2Bcamera%2Buvc&qid=1732315805&sprefix=usb%2Bcamera%2Buvc%2Caps%2C148&sr=8-40&th=1)). Using a non-UVC camera (most modern webcams, for example) will cause the vision program to crash due to image format incompatibilities.

>[!NOTE]
> The detection program works best with good lighting and non-glossy objects against a non-glossy background with good color-contrast versus the colors of the objects being detected. Ideally the objects are between 6 and 24 inches away from the camera lens (depends on size of object). 

* Plug your USB camera into a USB port on the STM32MP135F-DK

## Step 4: Run the AI Vision Demo

* Make sure you are in the correct directory by executing this command:
```
cd /home/weston
```

* Run the demo with this command:
```python3 MP135-vision-demo.py 0.6```

>[!NOTE]
>The "0.6" at the end of the command is the minimum confidence threshold for object detection. It is recommended to make this value between 0.5 and 0.8. Leaving the option blank defaults to 0.7 (70% confidence).

* The vision program is trained to recognize any object in [this list](object-labels.txt) but from our experimentation, some of the most consistently-detected and conveniently-sized objects to use are:
```
apple
orange
banana
donut
remote
scissors
cell phone
```
>[!NOTE]
>Instead of the physical objects, printing out decent-quality images of the objects onto paper (not glossy photograph paper) and putting those in front of the camera can result in detections of objects that typically would not be feasible for the demo (such as airplane, stop sign, giraffe, etc.). There have been mixed results with this, usually dependent on how life-like the images are.

>[!TIP]
>Adjusting the lighting, distance from the camera, background, and confidence threshold can help with more-consistent detection
