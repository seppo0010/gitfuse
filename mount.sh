#!/bin/bash
./umount.sh
PARAMS=""
if [ $# -eq 1 ]; then PARAMS="--mountunit=$1"; fi
/sw/bin/python2.6 src/index.py test/ $PARAMS
