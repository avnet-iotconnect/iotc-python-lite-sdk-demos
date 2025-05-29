#!/bin/sh

source /usr/local/x-linux-ai/resources/config_board_cpu.sh
cmd="python3 /usr/local/x-linux-ai/object-detection/iotc-vision-program.py -m /usr/local/x-linux-ai/object-detection/models/$OBJ_DETEC_MODEL -l /usr/local/x-linux-ai/object-detection/models/$OBJ_DETEC_MODEL_LABEL.txt --framerate $DFPS --frame_width $DWIDTH --conf_threshold $1 --frame_height $DHEIGHT $OPTIONS"
su -l weston -c "$cmd"
