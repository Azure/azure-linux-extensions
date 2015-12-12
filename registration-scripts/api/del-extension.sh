#!/bin/bash
original_dir=`pwd`
script=`dirname $0`
cd $script
source params
export script=`pwd`
cd $original_dir

curl -v -X 'DELETE'  -H "$VERSION" -H 'Content-Type: application/xml' -E $CERT $ENDPOINT/$SUBSCRIPTION/services/extensions/$1/$2/$3
