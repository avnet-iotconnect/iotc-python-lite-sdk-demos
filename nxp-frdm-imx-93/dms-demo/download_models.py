#
# Copyright 2020-2022 NXP
#
# SPDX-License-Identifier: Apache-2.0
#

import requests
import os
import tarfile
import shutil

def download_file(name, url, path, retry=3):
    if (os.path.exists(path)):
        os.unlink(path)
 
    print("Downloading ", name, " model(s) file(s) from", url)
    while (retry != 0):
        try:
            req = requests.get(url)
            break
        except Exception:
            retry -= 1
            print("Failed to download file from", url, "Retrying")
    with open(path, "wb") as f:
        f.write(req.content)

def decompress(path, model_dir):
    tar = tarfile.open(path, "r:gz")
    file_names = tar.getnames()
    for file_name in file_names:
        tar.extract(file_name, model_dir)
    tar.close()

def download_all_models(model_dir, vela_dir):
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(vela_dir, exist_ok=True)

    github_url = 'https://raw.githubusercontent.com/'

    #Download gesture models
    #https://github.com/PINTO0309/PINTO_model_zoo
    #url = 'https://drive.google.com/uc?export=download&&id=1yjWyXsac5CbGWYuHWYhhnr_9cAwg3uNI'
    #path = os.path.join(model_dir, 'gesture_models.tar.gz')
    #download_file('gesture recognition', url, path)
    #decompress(path, model_dir)

    #Download gesture models
    #https://github.com/terryky/tflite_gles_app
    url = github_url + 'terryky/tflite_gles_app/master/gl2handpose/handpose_model/'
    file_name = 'palm_detection_builtin_256_integer_quant.tflite'
    path = os.path.join(model_dir, file_name)
    download_file('hand landmark', url + file_name, path)
    file_name = 'hand_landmark_3d_256_integer_quant.tflite'
    path = os.path.join(model_dir, file_name)
    download_file('hand detection', url + file_name, path)

    #Download face recognition models
    #https://github.com/imuncle/yoloface-50k
    url = github_url + 'imuncle/yoloface-50k/main/tflite/yoloface_int8.tflite'
    path = os.path.join(model_dir, 'yoloface_int8.tflite')
    download_file('face detection', url, path)

    #https://github.com/shubham0204/FaceRecognition_With_FaceNet_Android
    url = github_url + 'shubham0204/FaceRecognition_With_FaceNet_Android/master/app/src/main/assets/facenet_512_int_quantized.tflite'
    path = os.path.join(model_dir, 'facenet_512_int_quantized.tflite')
    download_file('face recognition', url, path)

    #Download object detection model
    #https://www.tensorflow.org/
    #url link broken, inserted new link on 02/20/2025
    #url = 'https://storage.googleapis.com/tfhub-lite-models/tensorflow/lite-model/ssd_mobilenet_v1/1/metadata/2.tflite'
    url = 'https://tfhub.dev/tensorflow/lite-model/ssd_mobilenet_v1/1/default/1?lite-format=tflite'
    path = os.path.join(model_dir, 'ssd_mobilenet_v1_quant.tflite')
    download_file('object detection', url, path)

    #Download image classification model
    #https://www.tensorflow.org/
    url = 'http://download.tensorflow.org/models/mobilenet_v1_2018_08_02/mobilenet_v1_1.0_224_quant.tgz'
    path = os.path.join(model_dir, 'mobilenet_v1_1.0_224_quant.tgz')
    download_file('image classification', url, path)
    decompress(path, model_dir)

    #Download dms models
    #https://github.com/terryky/tflite_gles_app
    url = github_url + 'terryky/tflite_gles_app/master/gl2facemesh/facemesh_model/'
    file_name = 'face_detection_front_128_full_integer_quant.tflite'
    path = os.path.join(model_dir, file_name)
    download_file('DMS face detection', url + file_name, path)
    file_name = 'face_landmark_192_full_integer_quant.tflite'
    path = os.path.join(model_dir, file_name)
    download_file('DMS face landmark', url + file_name, path)

    #https://github.com/PINTO0309/PINTO_model_zoo
    url = "https://s3.ap-northeast-2.wasabisys.com/pinto-model-zoo/049_iris_landmark/resources.tar.gz"
    path = os.path.join(model_dir, 'dms_iris_landmark.tar.gz')
    download_file("dms iris landmark", url, path)
    decompress(path, model_dir)
    # Add extra decompression step to access required model
    path = os.path.join(model_dir, '20_new_20211209/resources.tar.gz')
    decompress(path, model_dir)
    shutil.copyfile("/usr/bin/eiq-examples-git/models/saved_model_64x64/model_integer_quant.tflite", "/usr/bin/eiq-examples-git/models/iris_landmark_quant.tflite")

def convert_model(model_dir, vela_dir):
    for name in os.listdir(model_dir):
        if name.endswith(".tflite"):
            print('Converting', name)
            model = os.path.join(model_dir, name)
            os.system('vela ' + model + " --output-dir " + vela_dir)

model_dir = '/usr/bin/eiq-examples-git/models'
vela_dir = '/usr/bin/eiq-examples-git/vela_models'
download_all_models(model_dir, vela_dir)
convert_model(model_dir, vela_dir)
