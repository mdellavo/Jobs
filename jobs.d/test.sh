#!/bin/bash

x=1
while [ $x -le 10 ]
do
    date
    sleep 1
    x=$(( $x + 1 ))
done

