#!/bin/bash
# run print script in venv as root
# necessary due need to access "local printer" devices inside
# this script must be set as executable and its path added into "sudoers"

if [ "`id -u`" -ne 0 ]; then
  # get path where we are
  MY_PATH=`dirname "${0}"`
  MY_PATH=`( cd "${MY_PATH}" && pwd )`
  echo "Switching from `id -un` to root"
  exec sudo "${0}" "${1}" "${MY_PATH}"
  exit 99
fi

# now commands...
# activate python venv
source "${2}/venv/bin/activate"
# get hhprint.py or hhprint4.py and pass params
if [ -e "${2}/hhprint4.py" ]; then
  exec python3 "${2}/hhprint4.py" "${1}"
else
  if [ -e "${2}/hhprint.py" ]; then
    exec python3 "${2}/hhprint.py" "${1}"
  fi
fi
# turn venv off
deactivate
