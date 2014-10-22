#!/bin/bash

for i in $(seq 1500)
do
    echo `date` + The script is running...
    >&2 echo `date` + ERROR:The script is running...
    sleep 1
done
