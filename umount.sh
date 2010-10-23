#/bin/sh
PARAMS=""
if [ $# -eq 1 ]; then PARAMS="dir"; fi
umount $PARAMS>/dev/null 2>/dev/null
killall python2.6>/dev/null 2>/dev/null
