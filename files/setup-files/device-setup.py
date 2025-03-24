import sys
import subprocess
import json
import os
import urllib.request
from getpass import getpass
import re
import argparse
import datetime

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

def get_device_id():
    while True:
        device_id = input('Enter a unique ID for your device (only alphanumeric chars and non-endcap hyphens allowed):')
        if re.match(r'^[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*$', device_id):
            return device_id
        print('The unique ID can only include alphanumeric characters and non-endcap hyphens. Please try again.')


# Get the current version of Python
version = sys.version_info
# Check if the major version is 3 and the minor version is at least 11
if version.major != 3 or version.minor < 11:
    print(f'Python version must be at least 3.11. Detected version is {version.major}.{version.minor}!')
    sys.exit(1)

# Check list of installed packages
result = subprocess.check_output([sys.executable, "-m", "pip", "list"], stderr=subprocess.PIPE)
installed_packages = result.decode('utf-8')

# Remove python package that has dependencies that conflict with IoTConnect libararies
if 'azure-iot-device' in installed_packages.lower():
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'uninstall', '-y', 'azure-iot-device'])
    except subprocess.CalledProcessError as e:
        print(f'Error occurred while uninstalling azure-iot-device: {e}')

# Using pip to install or force reinstall the Lite SDK
install = True
if 'iotconnect-sdk-lite' in installed_packages.lower():
    while True:
        y_or_n = input('iotconnect-sdk-lite is already installed. Would you like to force-reinstall it with the newest available version? (answer with y/Y/n/N)')
        if y_or_n in ['y', 'Y']:
            break
        elif y_or_n in ['n', 'N']:
            install = False
            break
        else:
            print('Invalid response, please only use y or Y for yes and n or N for No.')
if install == True:
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', '--force-reinstall', 'iotconnect-sdk-lite'])
    except subprocess.CalledProcessError as e:
        print(f'Error occurred while installing the Lite SDK: {e}')
        sys.exit(1)
  
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

import avnet.iotconnect.restapi.lib.template as template
from avnet.iotconnect.restapi.lib.error import InvalidActionError
from avnet.iotconnect.restapi.lib.template import TemplateCreateResult
from avnet.iotconnect.restapi.lib import device, config
import avnet.iotconnect.restapi.lib.credentials as credentials
import avnet.iotconnect.restapi.lib.apiurl as apiurl
from avnet.iotconnect.restapi.lib.apirequest import Headers, request

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

# Generate certificate/key
subj = '/C=US/ST=IL/L=Chicago/O=IoTConnect/CN=device'
days = 36500  # 100 years
ec_curve = 'prime256v1'
try:
    subprocess.check_call(['openssl', 'ecparam', '-name', ec_curve, '-genkey', '-noout', '-out', 'device-pkey.pem'])
    subprocess.check_call(['openssl', 'req', '-new', '-days', str(days), '-nodes', '-x509', '-subj', subj, '-key', 'device-pkey.pem', '-out', 'device-cert.pem'])
    print('X509 credentials are now generated as device-cert.pem and device-pkey.pem.')
except subprocess.CalledProcessError as e:
    print(f'An error occurred while generating certificates: {e}', file=sys.stderr)
    sys.exit(1)

# Create IOTC template
t = template.get_by_template_code('plitedemo')
if t is not None:
    print('plitedemo template already exists in IOTC instance, skipping to device creation.')
else:
    print('plitedemo template not detected in IOTC instance. Adding it now...')
    create_result: TemplateCreateResult = template.create('plitedemo_template.JSON', new_template_code='plitedemo', new_template_name='plitedemo')
    if create_result is None:
        raise Exception("Expected successful template creation")

# Create IOTC Device
with open('device-cert.pem', 'r') as file:
    certificate = file.read()
    while True:
        device_id = get_device_id()
        try:
            result = device.create(template_guid=t.guid, duid=device_id, device_certificate=certificate)
            print('create=', result)
            break
        except TypeError:
            # TypeError is usually been about credentials expiring mid-session and becoming a None-type
            print('There was a processing issue with your credentials, please re-enter them below.') 
            configure_creds()
            try:
                result = device.create(template_guid=t.guid, duid=device_id, device_certificate=certificate)
                print('create=', result)
                break
            except Exception as e:
                print(f"An exception occurred while attempting to create the device, please try again.: {e}")
        except Exception as e:
            print(f"An exception occurred while attempting to create the device, please try again.: {e}")

# Create device config
device_config = config.generate_device_json(device_id)
with open('iotcDeviceConfig.json', 'w') as f:
    f.write(device_config)

# Download app.py
try:
    urllib.request.urlretrieve('https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/files/core-files/app.py', 'app.py')
    print('app.py successfully downloaded. Run it with "python3 app.py".')
except Exception as e:
    print(f'Error downloading app file: {e}')
