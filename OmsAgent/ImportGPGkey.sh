#!/bin/sh

if [ -z "$1" ]; then
    echo "Usage:"
    echo "   $0 PUBLIC_GPG_KEY"
    exit 1
fi

if [ -z "$2" ]; then
    KEYRING_NAME="keyring.gpg"
else
    KEYRING_NAME=$2
fi

TARGET_DIR="$(dirname $1)"
HOME=$TARGET_DIR gpg --no-default-keyring --keyring $TARGET_DIR/$KEYRING_NAME --import $1
RETVAL=$?

# chown omsagent $TARGET_DIR/$KEYRING_NAME

exit $RETVAL