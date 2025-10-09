# Onboarding a Device to /IOTCONNECT via Online User Interface

Follow these steps on onboard your device into /IOTCONNECT via the online user interface.

1. In a web browser, navigate to console.iotconnect.io and log into your account.

2. In the blue toolbar on the left edge of the page, hover over the "processor" icon and then in the resulting dropdown
   select "Device".

3. Now in the resulting Device page, click on the "Templates" tab of the blue toolbar at the bottom of the screen.

4. Right-click and then click "save link as" on [this link to the default device template](https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/common/templates/plitedemo-template.json)
   to download the raw template file.

5. Back in the /IOTCONNECT browser tab, click on the "Create Template" button in the top-right of the screen.

6. Click on the "Import" button in the top-right of the resulting screen.

7. Select your downloaded copy of the plitedemo template from sub-step 4 and then click "save".

8. Click on the "Devices" tab of the blue toolbar at the bottom of the screen.

9. In the resulting page, click on the "Create Device" button in the top-right of the screen.

10. Customize the "Unique ID" and "Device Name" fields to your needs.

11. Select the most appropriate option for your device from the "Entity" dropdown (only for organization, does not
    affect connectivity).

12. Select "plitedemo" from the "Template" dropdown.

13. In the resulting "Device Certificate" field, make sure "Auto-generated" is selected.

14. Click the "Save and View" buton to go to the page for your new device.

15. Click on "Connection Info" on the right side of the device page above the processor icon.

16. In the resulting pop-up, click on the yellow/green certificate icon to download a zip file containing your device's
    certificates, and then close the pop-up.

17. Extract the zip folder and then rename the ```.pem``` file to ```device-pkey.pem``` and the ```.crt``` file to
    ```device-cert.crt```.

18. Still on your host machine, use this command within the unzipped certificates folder to convert the ```.crt``` file
    to another ```.pem``` file (application is expecting ```.pem``` files):

```
openssl x509 -in device-cert.crt -out device-cert.pem -outform PEM
```

> [!NOTE]
> If you are using a Windows host machine, this command is most easily performed via Git Bash. Using CMD or Powershell
> may require additional configuration of openssl.

19. Back in your device's page in /IOTCONNECT, click on the black/white/green paper-and-cog icon in the top-right of the
    device page (just above "Connection Info") to download your device's configuration file.

20. Using SCP (or WinSCP) copy these 3 files into the ```/home/weston/demo``` directory of your board:
    * device-cert.pem
    * device-pkey.pem
    * iotcDeviceConfig.json

> [!IMPORTANT]
> These files must be copied **individually** into the ```/home/weston/demo``` directory. They cannot be wrapped inside
> of another folder.

21. In the terminal of your board, navigate to the ```/home/weston/demo``` directory and then run this command to
    download the basic quickstart /IOTCONNECT application called ```app.py```:

```
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/stm32mp157f-dk2/starter-demo/src/app.py -O app.py
```