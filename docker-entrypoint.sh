#!/bin/sh
# Hands /data to user 1000 when started as root, then runs as that user.
set -e
if [ "$(id -u)" = 0 ]; then
  chown -R 1000:1000 /data
  exec setpriv --reuid=1000 --regid=1000 --clear-groups "$@"
fi
exec "$@"
