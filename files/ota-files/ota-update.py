# SPDX-License-Identifier: MIT
# Copyright (C) 2025 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

import tarfile
import os
import shutil
import sys
from http import HTTPMethod, HTTPStatus
import subprocess
from getpass import getpass
import datetime


# Compresses all relevant files into a .tar.gz to be used for OTA deployment 
def create_ota_payload():
    # Get the current directory (the directory where the script is located)
    script_dir = os.path.dirname(os.path.realpath(__file__))
    # Define the paths for the core-files, additional-files, and install.sh
    core_files_dir = os.path.join(script_dir, '..', 'core-files')
    additional_files_dir = os.path.join(script_dir, '..', 'additional-files')
    install_sh = os.path.join(script_dir, 'install.sh')
    # Define the tar.gz output file name
    output_tar_gz = os.path.join(script_dir, 'ota-payload.tar.gz')
    # Create a .tar.gz file
    with tarfile.open(output_tar_gz, 'w:gz') as tar:
        # Add files from core-files directory
        if os.path.exists(core_files_dir):
            for root, _, files in os.walk(core_files_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Add each file without its directory path
                    tar.add(file_path, arcname=file)
        # Add files from additional-files directory, excluding placeholder.txt
        if os.path.exists(additional_files_dir):
            for root, _, files in os.walk(additional_files_dir):
                for file in files:
                    if file != 'placeholder.txt':  # Skip placeholder.txt
                        file_path = os.path.join(root, file)
                        # Add each file without its directory path
                        tar.add(file_path, arcname=file)
        # Add the install.sh file
        if os.path.exists(install_sh):
            tar.add(install_sh, arcname='install.sh')


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

# Check if the REST API is installed, and install it if its not
def install_iotc_api():
    # Get the current version of Python
    version = sys.version_info
    # Check if the major version is 3 and the minor version is at least 11
    if version.major != 3 or version.minor < 11:
        print(f'Python version must be at least 3.11. Detected version is {version.major}.{version.minor}!')
        sys.exit(1)
    # Check list of installed packages
    result = subprocess.check_output([sys.executable, "-m", "pip", "list"], stderr=subprocess.PIPE)
    installed_packages = result.decode('utf-8')
    # Using pip to install or force reinstall the API
    install = True
    if 'iotconnect-rest-api' in installed_packages.lower():
        while True:
            y_or_n = input('iotconnect-rest-api is already installed. Would you like to force-reinstall it with the newest available version? (answer with y/Y/n/N)')
            if y_or_n in ['y', 'Y']:
                break
            elif y_or_n in ['n', 'N']:
                install = False
                break
            else:
                print('Invalid response, please only use y or Y for yes and n or N for No.')
    if install == True:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', '--force-reinstall', 'iotconnect-rest-api'])
            print('iotconnect-rest-api has been successfully installed.')
        except subprocess.CalledProcessError as e:
            print(f'Error occurred while installing iotconnect-rest-api: {e}')
            sys.exit(1)


# Create a FW upgrade for the associated template and get its GUID
def get_fw_upgrade_guid(template_code: str):
    # Check if specified template has firmware associated with it already
    t = template.get_by_template_code(template_code)
    # If no firmware exists for the template
    if t.firmwareGuid == None:
        print("Template does not have firmware")
        # Create new firmware for the template
        while True:
            firmware_name = input('Please enter a name for the firmware. It should be between 1 and 10 characters, all uppercase and alphanumeric.')
            try:
                firmware._validate_firmware_name(firmware_name)
                break
            except UsageError as e:
                print(f'Invalid firmware name, please try again: {e}')
        firmware_create_result = firmware.create(template_guid=t.guid, name=firmware_name, hw_version="1.0", initial_sw_version="v1.0", description="Initial version")
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

# Check if the REST API is installed, and install it if its not
install_iotc_api()

# Now that the REST API is installed, its relevant libraries can be imported
import avnet.iotconnect.restapi.lib.template as template
from avnet.iotconnect.restapi.lib import firmware, upgrade, device, config, ota, apiurl, util
from avnet.iotconnect.restapi.lib.apirequest import request
import avnet.iotconnect.restapi.lib.credentials as credentials
from avnet.iotconnect.restapi.lib.error import UsageError

# Compress relevant files into payload .tar.gz
create_ota_payload()

# Get the device GUID(s) that will receive the OTA, and the template code they use
device_guid_list, template_code = get_device_guids_and_template_code()

# Create a FW upgrade for the associated template and get its GUID
fw_upgrade_guid = get_fw_upgrade_guid(template_code)

# Upload the payload file to the FW upgrade
upgrade.upload(fw_upgrade_guid, 'ota-payload.tar.gz', file_name='ota-payload.tar.gz')

# Publish the firmware upgrade so it can be sent via OTA
upgrade.publish(fw_upgrade_guid)

ota.push_to_device(fw_upgrade_guid, device_guid_list)
print("Successful OTA push!")
