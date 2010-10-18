#/bin/sh
umount test>/dev/null 2>/dev/null
killall python2.6
/sw/bin/python2.6 src/index.py test/
