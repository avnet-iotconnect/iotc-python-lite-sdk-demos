# SPDX-License-Identifier: MIT
# Copyright (C) 2025 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

import sys
import subprocess
import urllib.request
import re
import avnet.iotconnect.restapi.lib.template as template
from avnet.iotconnect.restapi.lib import device, config

'''
Assumptions before running this script:
1) The IoTConnect REST API is already installed on this device
2) The IoTConnect Python Lite SDK is already installed on this device
3) The user is currently logged into their IoTConnect account on this machine via the REST API CLI


Script Flow:
1) A new certificate and private key are generated for this device
2) If the "plitedemo" template does not already exist for this IOTC entity, it is created
3) The user inputs a valid unique ID for the device and it is created
4) A config file is generated for the device
5) The basic starter IOTC python program is downloaded to this device
'''

# Prompts user for a unique device ID and verifies that it is a valid entry
def get_input_device_id():
    while True:
        device_id = input('Enter a unique ID for your device (only alphanumeric chars and non-endcap hyphens allowed):')
        if re.match(r'^[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*$', device_id):
            return device_id
        print('The unique ID can only include alphanumeric characters and non-endcap hyphens. Please try again.')


#----------------MAIN---------------------

# Generate certificate and private key for device
subj = '/C=US/ST=IL/L=Chicago/O=IoTConnect/CN=device'
days = 36500  # 100 years
ec_curve = 'prime256v1'
subprocess.check_call(['openssl', 'ecparam', '-name', ec_curve, '-genkey', '-noout', '-out', 'device-pkey.pem'])
subprocess.check_call(['openssl', 'req', '-new', '-days', str(days), '-nodes', '-x509', '-subj', subj, '-key', 'device-pkey.pem', '-out', 'device-cert.pem'])
print('X509 credentials are now generated as device-cert.pem and device-pkey.pem.')

# Create plitedemo template if it does not exist in this entity
t = template.get_by_template_code('plitedemo')
if t is None:
    print('plitedemo template not detected in IOTC instance. Adding it now...')
    create_result = template.create('plitedemo_template.JSON')
    t = template.get_by_template_code(template_code)

# Create IOTC Device
with open('device-cert.pem', 'r') as file:
    # Previously-generated certificate is used in device creation
    certificate = file.read()
    # Loop breaks once device is successfully created
    while True:
        # User inputs a valid unique ID
        device_id = get_input_device_id()
        try:
            # Attempt device creation
            result = device.create(template_guid=t.guid, duid=device_id, device_certificate=certificate)
            # If no exceptions, exit loop
            break
        # Most common exception will be for the given unique ID already being in use
        except Exception as e:
            print(f"An exception occurred while attempting to create the device, please try again.: {e}")

# Create device config file
device_config = config.generate_device_json(device_id)
with open('iotcDeviceConfig.json', 'w') as f:
    f.write(device_config)

# Download app.py
urllib.request.urlretrieve('https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/files/core-files/app.py', 'app.py')
print('app.py successfully downloaded. Run it with "python3 app.py".')
