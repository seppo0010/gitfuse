#!/bin/bash
./umount.sh
PARAMS=""

export GITPYTHON_TEST_DIR=testdir
export GITPYTHON_TEST_REPO_DIR=~/.gitfuseunittest
export GITPYTHON_TEST_REPO_NAME=unittest

rm -rf $GITPYTHON_TEST_REPO_DIR
mkdir $GITPYTHON_TEST_REPO_DIR
git init -q $GITPYTHON_TEST_REPO_DIR

rm -rf $GITPYTHON_TEST_DIR
mkdir $GITPYTHON_TEST_DIR

./mount.sh $GITPYTHON_TEST_DIR --mountunit=$GITPYTHON_TEST_REPO_NAME
python2.6 src/test.py
./umount.sh $GITPYTHON_TEST_DIR
