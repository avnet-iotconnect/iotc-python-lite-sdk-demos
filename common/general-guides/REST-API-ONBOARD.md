# Onboarding a Device to /IOTCONNECT via REST API (Requires Solution Key)

> [!IMPORTANT]
> The /IOTCONNECT REST API requires Python version 3.11 or newer to function due to its dependency on several features added 
> to the http Python library in version 3.11. If your device is running an earlier version of Python, you can onboard your 
> device through the /IOTCONNECT online user interface by following the steps laid out in the "Onboard Device" section of 
> your device's QuickStart.

Utilizing the REST API requires a solution key which must be obtained by contacting Softweb Solutions or by requesting it 
via ticket in the online /IOTCONNECT user interface.

Once you have obtained your account's solution key, proceed with the following steps to onboard your device into /IOTCONNECT.

1. Run this command on your device to install the /IOTCONNECT REST API python module:
```
python3 -m pip install iotconnect-rest-api
```

2. Now run this command on your device to protect your /IOTCONNECT credentials (prevents device history from saving them):
```
export HISTCONTROL=ignoreboth
```

3. Then run this /IOTCONNECT REST API CLI command (with your credentials substituted in) to log into your /IOTCONNECT account on the device:
```
iotconnect-cli configure -u my@email.com -p "MyPassword" --pf mypf --env myenv --skey=mysolutionkey
```
For example if these were your credentials:
* Email: `john.doe@gmail.com`
* Password: Abc123!
* Platform: aws
* Environment: technology
* Solution Key: AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
     
Your login command would be:
```
iotconnect-cli configure -u john.doe@gmail.com -p "Abc123!" --pf aws --env technology --skey=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
```
You will see this output in the console if your login succeeded:
```
Logged in successfully.
```

4. Lastly, run this command to download and run the device setup script:
```
curl -sOJ 'https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/common/scripts/device-setup.py' && python3 device-setup.py
```

After answering the prompts given by the device setup script, your device will be automatically onboarded into /IOTCONNECT.

You can verify this by logging into the online /IOTCONNECT user interface and locating your new device in the "Device" list.