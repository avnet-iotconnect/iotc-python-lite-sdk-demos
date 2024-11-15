import os
import sys
from setuptools import setup

packages_requires=[]

if 'win' in sys.platform:
    if sys.version_info >= (3, 5):
        packages_requires=["paho-mqtt","ntplib","pypiwin32"]
    else:
        packages_requires=[]
        os.system('pip install paho-mqtt')
        os.system('pip install ntplib')
        os.system('pip install pypiwin32')
        #os.system('pip install jsonlib')


elif 'linux' in sys.platform :
    if sys.version_info >= (3, 5):
        packages_requires=["ntplib"]
    else:
        packages_requires=[]
        os.system('pip install paho-mqtt')
        os.system('pip install ntplib')
        os.system('pip install jsonlib')
 
setup(
    name="iotconnect-sdk",
    version="1.1",
    python_requires=">=2.7,>=3.5,<3.100",
    description='SDK for D2C and C2D communication',
    license="MIT",
    author='SOFTWEB SOLUTIONS<admin@softwebsolutions.com> (https://www.softwebsolutions.com)',
    packages=["iotconnect", "iotconnect.client", "iotconnect.common"],
    install_requires=packages_requires,
    package_data={'iotconnect': ['assets/*.*']},
    platforms=['Linux', 'Mac OS X', 'Win'],
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: MIT License",
        "Operating System :: OS Independent"
    ],
)
