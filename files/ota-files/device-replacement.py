import sys
import json
from avnet.iotconnect.restapi.lib import device, template

template_code = sys.argv[1]
template_json_name = template_code + '_template.JSON'

# Read and store the DUID of the existing device
with open('iotcDeviceConfig.json', 'r') as file:
  device_config = json.load(file)
  duid = device_config.get('did')

# Create given template if it does not exist in this entity
t = template.get_by_template_code(template_code)
if t is None:
    print(f'template {template_code} not detected in IOTC instance. Adding it now...')
    result = template.create(template_json_name, new_template_code=template_code, new_template_name=template_code)
    t = template.get_by_template_code(template_code)

# Create new IOTC Device with desired template
with open('device-cert.pem', 'r') as file:
    # Previously-generated certificate is used in device creation
    certificate = file.read()
    result = device.create(template_guid=t.guid, duid=duid, device_certificate=certificate)
