import tarfile
import os
import shutil
import sys
import avnet.iotconnect.restapi.lib.template as template
from avnet.iotconnect.restapi.lib import firmware, upgrade, device, config, ota, apiurl, util
from avnet.iotconnect.restapi.lib.error import InvalidActionError, ConflictResponseError
from avnet.iotconnect.restapi.lib.apirequest import request
import avnet.iotconnect.restapi.lib.credentials as credentials
from http import HTTPMethod, HTTPStatus
import subprocess
from getpass import getpass
import datetime

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

def configure_creds():
    while True:
        try:
            email = input('Enter your IOTC login email address: ')
            psswd = getpass('Enter your IOTC login password: ')
            solutionkey = input('Enter your IOTC solution key (if you do not know your solution key, you can request it via a support ticket on the IoTConnect online platform): ')
            platform = input('Enter your IOTC platform (az for Azure or aws for AWS): ')
            environment = input('Enter your IOTC environment (can be found in the Key Vault of the IoTConnect online platform): ')
            config.env = environment
            config.pf = platform
            config.skey = solutionkey
            apiurl.configure_using_discovery()
            credentials.authenticate(username=email, password=psswd)
            break
        except Exception as e:
            print(f'Error processing credentials, please try again: {e}')

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

# Check login status and get user credentials if logged out
logged_in = True
if config.access_token is None:
        logged_in = False
else:
    if config.token_expiry < datetime.datetime.now(datetime.timezone.utc).timestamp():
        logged_in = False
    elif config.token_time + 3600 < datetime.datetime.now(datetime.timezone.utc).timestamp() and os.environ.get('IOTC_API_NO_TOKEN_REFRESH') is None:
        # It's been longer than an hour since we refreshed the token. We should refresh it now.
        data = {
        "refreshtoken": config.refresh_token
        }
        response = request(apiurl.ep_auth, "/Auth/refresh-token", json=data, headers={})
        config.access_token = response.body.get_object_value("access_token")
        config.refresh_token = response.body.get_object_value("refresh_token")
        expires_in = response.body.get_object_value("expires_in")
        config.token_time = datetime.datetime.now(datetime.timezone.utc).timestamp()
        config.token_expiry = config.token_time + expires_in
        config.write()
if logged_in == True:
    print('Already logged into IoTConnect on this device.')
else:    
    print('To use the IoTConnect API, you will need to enter your credentials. These will be stored for 24 hours and then deleted from memory for security.') 
    configure_creds()

create_ota_payload()

TEMPLATE_CODE = 'plitedemo'
FIRMWARE_NAME = 'PLITEDEMO'

# Get the device(s) unique ID(s) and corresponding GUID(s)
device_guid_list = []
while True:
    duid = input('Enter the unique ID of the first device you wish to send this OTA to:')
    d = device.get_by_duid(duid)
    # If a device matching the given duid is found
    if d is not None:
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
            # Add its guid to the list
            device_guid_list.append(d.guid)
        else:
            print('No device found matching the given DUID. Please try again.')
    elif resp in ['n', 'N']:
        break
    else:
        print('Invalid response, please only use y/Y for yes and n/N for No.')

# Get template info (need GUID)
t = template.get_by_template_code(TEMPLATE_CODE)
try:
    # Attempt to create firmware for specified template
    firmware_create_result = firmware.create(template_guid=t.guid, name=FIRMWARE_NAME, hw_version="1.0", initial_sw_version="v1.0", description="Initial version")
    firmware_guid = firmware_create_result.newId
    # Get firmware upgrade GUID for the new firmware
    fw_upgrade_guid = firmware_create_result.firmwareUpgradeGuid
except Exception as e:
    if 'TemplateAlreadyAttachedWithFirmware' in str(e):
        print('A firmware already exists for the selected template, so this OTA update will be an upgrade for that existing firmware.')
        # Get existing firmware guid
        response = request(apiurl.ep_firmware, '/Firmware', params={"TemplateName": TEMPLATE_CODE}, codes_ok=[HTTPStatus.NO_CONTENT])
        firmware_info = response.data.get_one(dc=firmware.Firmware)
        firmware_guid = firmware_info.guid
        # Create an upgrade for existing firmware
        fw_upgrade_create_result = upgrade.create(firmware_guid=firmware_guid)
        fw_upgrade_guid = fw_upgrade_create_result.newId
    else:
        print(f'Error occurred while trying to create Firmware, exiting...: {e}')
        sys.exit(1)
        
# fw_upgrade_guid now points to the correct FW upgrade guid, regardless of if the firmware existed previously or not

# Upload the payload file to the upgrade
upgrade.upload(fw_upgrade_guid, 'ota-payload.tar.gz', file_name='ota-payload.tar.gz')
# Publish the firmware upgrade so it can be sent via OTA
upgrade.publish(fw_upgrade_guid)

try:
    ota.push_to_device(fw_upgrade_guid, device_guid_list)
    print("Successful OTA push!")
except ConflictResponseError:
    print("Failed OTA push!")
