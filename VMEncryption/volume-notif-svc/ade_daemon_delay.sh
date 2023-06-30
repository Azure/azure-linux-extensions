#!/usr/bin/env bash
path=$(pwd)
script=$1

sleeping=30
shim="$path/$script"
echo "$shim"
if [ -d $path ]; then
        echo $path is valid directory
else
        echo wrong direcotry
        exit 1
fi

if [ -f $shim ]; then
        echo $shim is valid file
else
        echo "wrong file.. exiting!"
        exit 1
fi
result=$(ps -aux|grep daemon|grep $shim)
#result=`ps -aux|grep daemon`
while [ "$result" != "" ]
do
        echo "still daemon is running, apply $sleeping second delay"
        sleep $sleeping
        result=$(ps -aux|grep daemon|grep $shim)
done
echo encryption is finished!