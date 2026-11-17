#!/bin/sh
set -eu
alembic upgrade head
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/opspilot.conf
