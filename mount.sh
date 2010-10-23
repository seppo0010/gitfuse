#!/bin/bash
./umount.sh
PARAMS=$*
if [ $# -eq 0 ]; then PARAMS="dir/ --mountunit=gitfusetest"; fi
python2.6 src/index.py $PARAMS
