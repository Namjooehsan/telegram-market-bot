#!/bin/sh
set -eu
if [ -d /data ]; then
  chown -R appuser:appuser /data
fi
exec gosu appuser "$@"
