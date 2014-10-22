#!/bin/bash

for i in {0, 150}
do
    echo `date` + The script is running...
    >&2 echo `date` + ERROR:The script is running...
    sleep 10
done
