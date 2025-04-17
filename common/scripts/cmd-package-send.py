# SPDX-License-Identifier: MIT
# Copyright (C) 2025 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

import requests
import uuid
import time
from avnet.iotconnect.restapi.lib import storage, command, device, template, apiurl
import sys
import urllib.request
from http import HTTPMethod


# Get user to input the DUIDs of all devices to receive the OTA, and extract the GUIDs from those
def get_device_guids_and_template_code():
    device_guid_list = []
    while True:
        duid = input('Enter the unique ID of the first device you wish to send this OTA to:')
        d = device.get_by_duid(duid)
        # If a device matching the given duid is found
        if d is not None:
            # Get the device template guid
            template_guid = d.deviceTemplateGuid
            t = template.get_by_guid(d.deviceTemplateGuid)
            template_code = t.templateCode
            # Add its guid to the list
            device_guid_list.append(d.guid)
            break
        else:
            print('No device found matching the given DUID. Please try again.')
    while True:
        resp = input('Is there another device you wish to send this OTA to? (y/Y or n/N)')
        if resp in ['y', 'Y']:
            duid = input('Enter the unique ID of the next device you wish to send this OTA to:')
            d = device.get_by_duid(duid)
            # If a device matching the given duid is found
            if d is not None:
                # If device template does not match previous devices
                if d.deviceTemplateGuid != template_guid:
                    print(duid + ' does not use the same template as previously entered devices. A single OTA can only be pushed to devices of a single template.')
                else:
                    # Add its guid to the list
                    device_guid_list.append(d.guid)
            else:
                print('No device found matching the given DUID. Please try again.')
        elif resp in ['n', 'N']:
            break
        else:
            print('Invalid response, please only use y/Y for yes and n/N for No.')
    return device_guid_list, template_code


# Ask if device template needs to change, and change accordingly
def update_template_selection(device_guid_list, template_code):
    while True:
        resp = input(f'The template code for the given devices is {template_code}. Does the template for the devices need to be changed? (y/Y or n/N)')
        if resp in ['y', 'Y']:
            new_template_code = input(f'Enter the template code you would like to switch the devices to:')
            t = template.get_by_template_code(new_template_code)
            if t is None:
                print(f'{new_template_code} template not detected in IOTC instance. Adding it now...')
                # Download template
                try:
                    urllib.request.urlretrieve(f'https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/common/templates/{new_template_code}-template.json', f'{new_template_code}-template.json')
                except Exception as e:
                    print(f'Error downloading selected IoTConnect template from github!: {e}')
                    sys.exit(1)
                create_result = template.create(f'{new_template_code}-template.json')
            # Get selected template GUID
            t = template.get_by_template_code(new_template_code)
            # API call to update template for every device in the list
            for dev_guid in device_guid_list:
                response = request(apiurl.ep_device, f'/device-template/{dev_guid}/updatedevicetemplate', json={"templateGuid": t.guid}, method=HTTPMethod.PUT)
            return new_template_code
        elif resp in ['n', 'N']:
            print(f'Devices will continue using the {template_code} template')
            return None
        else:
            print('Invalid response, please only use y/Y for yes and n/N for No.')


# Create GUID for files uploaded in this app
MY_APP_GUID = str(uuid.uuid4()).upper()

# Specify file type
MODULE_TYPE = storage.FILE_MODULE_FIRMWARE

# Upload local file
result = storage.create(MODULE_TYPE, MY_APP_GUID, file_path='../package.tar.gz')
print(result['file'])

# Get user to input the DUIDs of all devices to receive the file, and extract the GUIDs from those as well as the template GUID 
device_guid_list, template_code = get_device_guids_and_template_code()

new_template_code = update_template_selection(device_guid_list, template_code)
if new_template_code is not None:
    template_code = new_template_code

t = template.get_by_template_code(template_code)

# Retrieve info for file-download command
file_download_command = command.get_with_name(t.guid, 'file-download')

# For every device in the list, send the file-download command with the file URL
success = 0
failed = 0
for device_guid in device_guid_list:
    try:
        command.send(file_download_command.guid, device_guid, result['file'])
        print("Command successful!")
        success +=1
    except Exception as e:
        print(f"Error executing a command: {e}")
        failed += 1
print(f"Total successful commands: {success}")
print(f"Total failed commands: {failed}")
