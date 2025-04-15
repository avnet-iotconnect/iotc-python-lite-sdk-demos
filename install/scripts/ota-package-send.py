# SPDX-License-Identifier: MIT
# Copyright (C) 2025 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

import os
import sys
import avnet.iotconnect.restapi.lib.template as template
from avnet.iotconnect.restapi.lib import firmware, upgrade, device, ota, apiurl, util
import avnet.iotconnect.restapi.lib.credentials as credentials
from avnet.iotconnect.restapi.lib.error import UsageError
from http import HTTPMethod
from avnet.iotconnect.restapi.lib.apirequest import request
import time


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
    

# Create a FW upgrade for the associated template and get its GUID
def get_fw_upgrade_guid(template_code: str):
    # Check if specified template has firmware associated with it already
    t = template.get_by_template_code(template_code)
    # If no firmware exists for the template
    if t.firmwareGuid is None:
        print("Template does not have firmware")
        # Create new firmware for the template
        while True:
            firmware_name = input('Please enter a name for the firmware. It should be between 1 and 10 characters, all uppercase and alphanumeric.')
            try:
                firmware._validate_firmware_name(firmware_name)
                break
            except UsageError as e:
                print(f'Invalid firmware name, please try again: {e}')
        firmware_create_result = firmware.create(template_guid=t.guid, name=firmware_name, hw_version="1.0", description="Initial version")
        firmware_guid = firmware_create_result.newId
        # Get firmware upgrade GUID for the new firmware
        fw_upgrade_guid = firmware_create_result.firmwareUpgradeGuid
    # If there is existing firmware for the template
    else:
        # Create an upgrade for existing firmware
        print('A firmware already exists for the device template, so this OTA update will be an upgrade for that existing firmware.')
        fw_upgrade_create_result = upgrade.create(firmware_guid=t.firmwareGuid)
        fw_upgrade_guid = fw_upgrade_create_result.newId
    # fw_upgrade_guid now points to the correct FW upgrade guid, regardless of if the firmware existed previously or not
    return fw_upgrade_guid

    
#----------------MAIN---------------------

# Get the device GUID(s) that will receive the OTA, and the template code they use
device_guid_list, template_code = get_device_guids_and_template_code()

# If device template needs to change, change it
new_template_code = update_template_selection(device_guid_list, template_code)
if new_template_code is not None:
    template_code = new_template_code

# Create a FW upgrade for the associated template and get its GUID
fw_upgrade_guid = get_fw_upgrade_guid(template_code)

# Upload the payload file to the FW upgrade
upgrade.upload(fw_upgrade_guid, 'install-package.tar.gz')

# Publish the firmware upgrade so it can be sent via OTA
upgrade.publish(fw_upgrade_guid)

ota.push_to_device(fw_upgrade_guid, device_guid_list)
print("Successful OTA push!")
