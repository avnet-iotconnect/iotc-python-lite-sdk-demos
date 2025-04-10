# SPDX-License-Identifier: MIT
# Copyright (C) 2025 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

import requests
import uuid
import time
from avnet.iotconnect.restapi.lib import storage, command, device, template


# Get user to input the DUIDs of all devices to receive the file, and extract the GUIDs from those as well as the template GUID
def get_device_guids_and_template_guid():
    device_guid_list = []
    while True:
        duid = input('Enter the unique ID of the first device you wish to send this file to:')
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
        resp = input('Is there another device you wish to send this file to? (y/Y or n/N)')
        if resp in ['y', 'Y']:
            duid = input('Enter the unique ID of the next device you wish to send this file to:')
            d = device.get_by_duid(duid)
            # If a device matching the given duid is found
            if d is not None:
                # If device template does not match previous devices
                if d.deviceTemplateGuid != template_guid:
                    print(duid + ' does not use the same template as previously entered devices. A file can only be pushed to devices of a single template.')
                else:
                    # Add its guid to the list
                    device_guid_list.append(d.guid)
            else:
                print('No device found matching the given DUID. Please try again.')
        elif resp in ['n', 'N']:
            break
        else:
            print('Invalid response, please only use y/Y for yes and n/N for No.')
    return device_guid_list, template_guid


# Create GUID for files uploaded in this app
MY_APP_GUID = str(uuid.uuid4()).upper()

# Specify file type
MODULE_TYPE = storage.FILE_MODULE_FIRMWARE

# Upload local file
result = storage.create(MODULE_TYPE, MY_APP_GUID, file_path='ota-payload.tar.gz')
print(result['file'])

# Get user to input the DUIDs of all devices to receive the file, and extract the GUIDs from those as well as the template GUID 
device_guid_list, template_guid = get_device_guids_and_template_guid()

# Retrieve info for file-download command
file_download_command = command.get_with_name(template_guid, 'file-download')

# For every device in the list, send the file-download command with the file URL
for device_guid in device_guid_list:
    command.send(file_download_command.guid, device_guid, result['file'])
