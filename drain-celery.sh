#!/bin/bash

output=$(docker ps -qf "name=nmbl_nmblcelery")

if [ ! -z $output ]
then
  docker exec -i $output python drain_tasks.py 
else
  exit 1
fi
