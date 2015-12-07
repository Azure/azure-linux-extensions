#!/bin/bash
original_dir=`pwd`
script=`dirname $0`
cd $script
source params
export script=`pwd`
cd $original_dir

echo $1
curl -v -X 'POST'  -H "$VERSION" -H 'Content-Type: application/xml' -E $CERT -d@$1 $ENDPOINT/$SUBSCRIPTION/services/extensions
