#!/bin/bash

commitmessage=$(git log -1 --pretty=%B)
echo $commitmessage
regex='^\[ci skip\]'
if [[ $commitmessage =~ $regex ]];
then
    echo yes
else
    echo no
fi

