#!/bin/bash

x=1
while [ $x -le 60 ]
do
    date
    sleep 1
    x=$(( $x + 1 ))
done

