#!/bin/bash
# this is simplified version of printing script for executing from CLI
# you just need to pass codes in acceptable format

# get current path
MY_PATH=`dirname "${0}"`
MY_PATH=`( cd "${MY_PATH}" && pwd )`
exec "${MY_PATH}/hhprint.sh" "hhprint:print?codes=${1}"
