import sys
import subprocess
import json
import os
import avnet.iotconnect.restapi.lib.template as template
from avnet.iotconnect.restapi.lib.error import InvalidActionError
from avnet.iotconnect.restapi.lib.template import TemplateCreateResult
'''
# Get the current version of Python
version = sys.version_info
# Check if the major version is 3 and the minor version is at least 11
if version.major != 3 or version.minor < 11:
    print(f"Python version must be at least 3.11. Detected version is {version.major}.{version.minor}!")
    sys.exit(1)

# Using pip to install or force reinstall the Lite SDK
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall", "iotconnect-sdk-lite"])
except subprocess.CalledProcessError as e:
        print(f"Error occurred while installing the Lite SDK: {e}")
        sys.exit(1)
  
# Install API
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "iotconnect-rest-api"])
    print("iotconnect-rest-api has been successfully installed.")
except subprocess.CalledProcessError as e:
    print(f"Error occurred while installing iotconnect-rest-api: {e}")
    sys.exit(1)
  
# Get user credentials
print("To use the IoTConnect API, you will need to enter your credentials. These will be stored for 24 hours and then deleted from memory for security.") 
email = input("Enter your IOTC login email address: ")
password = input("Enter your IOTC login password: ")
solutionkey = input("Enter your IOTC solution key (if you don't know your solution key, you can request it via a support ticket on the IoTConnect online platform): ")
platform = input("Enter your IOTC platform (az for Azure or aws for AWS): ")
environment = input("Enter your IOTC environment (can be found in the 'Key Vault' of the IoTConnect online platform): ")
command = f'iotconnect-cli configure -u {email} -p "{password}" --pf {platform} --env {environment} --skey={solutionkey}'
try:
    subprocess.check_call(command, shell=True)
except subprocess.CalledProcessError as e:
    print(f"IoTConnect Credentials Error": {e}")
    sys.exit(1)

# Generate certificate/key
subj = "/C=US/ST=IL/L=Chicago/O=IoTConnect/CN=device"
days = 36500  # 100 years
ec_curve = "prime256v1"
try:
    subprocess.check_call(["openssl", "ecparam", "-name", ec_curve, "-genkey", "-noout", "-out", "device-pkey.pem"])
    subprocess.check_call(["openssl", "req", "-new", "-days", str(days), "-nodes", "-x509", "-subj", subj, "-key", "device-pkey.pem", "-out", "device-cert.pem"])
        print("X509 credentials are now generated as device-cert.pem and device-pkey.pem.")
except subprocess.CalledProcessError as e:
    print(f"An error occurred while generating certificates: {e}", file=sys.stderr)
    sys.exit(1)
'''

# Create IOTC template
t = template.get_by_template_code('plitedemo')
if t is not None:
    print("Standard device template not detected in IOTC instance. Adding it now...")
    create_result: TemplateCreateResult = template.create('sample-device-template.json', new_template_code="plitedemo", new_template_name="plitedemo")
    if create_result is None:
        raise Exception("Expected successful template creation")


# create device

# get device config

# download app.py
