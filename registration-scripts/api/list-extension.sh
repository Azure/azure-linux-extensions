#!/bin/bash
original_dir=`pwd`
script=`dirname $0`
cd $script
source params
export script=`pwd`
cd $original_dir

curl -v -X 'GET' -H 'x-ms-version: 2014-06-01' -H 'Content-Type: application/xml' -E $CERT $ENDPOINT/$SUBSCRIPTION/services/publisherextensions
