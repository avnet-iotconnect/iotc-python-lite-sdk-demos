# Push Package via OTA From Host Machine Console

Pushing an OTA from your local machine requires you to be logged into your /IOTCONNECT account so it can utilize the
/IOTCONNECT REST API.

First make sure you install the /IOTCONNECT REST API Python module to your host machine:

```
python3 -m pip install iotconnect-rest-api
```

Run this command to protect your /IOTCONNECT credentials:

```
export HISTCONTROL=ignoreboth
```

Then run this /IOTCONNECT REST API CLI command (with your credentials substituted in) to log into your /IOTCONNECT account
on the device:

```
iotconnect-cli configure -u my@email.com -p "MyPassword" --pf mypf --env myenv --skey=mysolutionkey
```

For example if these were your credentials:

* Email: john.doe@gmail.com
* Password: Abc123!
* Platform: aws
* Environment: technology
* Solution Key: AbCdEfGhIjKlMnOpQrStUvWxYz1234567890

Your login command would be:

```
iotconnect-cli configure -u john.doe@gmail.com -p "Abc123!" --pf aws --env technology --skey=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
```

> [!IMPORTANT]
> Notice that the password argument of the command is **the only argument that is in quotes.** Make sure you pay
> attention
> to this detail.

You will see this output in the console if your login succeeded:

```
Logged in successfully.
```

Navigate into the ```/common/scripts/``` directory of you cloned repo and run this command:

```
python3 ota-package-send.py
```

You will be prompted to enter the unique IDs of the devices you wish to send the OTA package to. If the firmware for
your
listed devices does not yet have an associated firmware, you will also be prompted for a name for the new firmware to be
created.

The ```package.tar.gz``` file you generated previously will be automatically uploaded to an upgrade for the new/existing
firmware, and the OTA package will be automatically pushed.

You should then see this output in your host machine console:

```
Successful OTA push!
```

# Push Package Through Command From Host Machine Console

Pushing an package from your local machine requires you to be logged into your /IOTCONNECT account so it can utilize the
/IOTCONNECT REST API.

First make sure you install the /IOTCONNECT REST API Python module to your host machine:

```
python3 -m pip install iotconnect-rest-api
```

Run this command to protect your /IOTCONNECT credentials:

```
export HISTCONTROL=ignoreboth
```

Then run this /IOTCONNECT REST API CLI command (with your credentials substituted in) to log into your /IOTCONNECT account
on the device:

```
iotconnect-cli configure -u my@email.com -p "MyPassword" --pf mypf --env myenv --skey=mysolutionkey
```

For example if these were your credentials:

* Email: john.doe@gmail.com
* Password: Abc123!
* Platform: aws
* Environment: technology
* Solution Key: AbCdEfGhIjKlMnOpQrStUvWxYz1234567890

Your login command would be:

```
iotconnect-cli configure -u john.doe@gmail.com -p "Abc123!" --pf aws --env technology --skey=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
```

> [!IMPORTANT]
> Notice that the password argument of the command is **the only argument that is in quotes.** Make sure you pay
> attention to this detail.

You will see this output in the console if your login succeeded:

```
Logged in successfully.
```

Navigate into the ```/common/scripts/``` directory of you cloned repo and run this command:

```
python3 cmd-package-send.py
```

You will be prompted to enter the unique IDs of the devices you wish to send the package to. All of the devices must use
the same template. Any devices that use a template different from the first device entered will be rejected.

After entering your device IDs, the ```package.tar.gz``` file you generated previously will be automatically uploaded
and
the command will be automatically pushed to all given devices.

For every device that receives the command, you should see this output in your host machine console:

```
Command successful!
```

After the command is sent to all given devices, you will see a tally of successful and failed commands in your host
machine console as well.