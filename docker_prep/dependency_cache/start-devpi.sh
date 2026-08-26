#!/usr/bin/env bash
set -euo pipefail
SERVERDIR=/cache/devpi
if [ ! -f "$SERVERDIR/.serverversion" ]; then
  devpi-init --serverdir "$SERVERDIR"
fi
configure_devpi_mirror() {
  local tries=0
  until NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost devpi use http://127.0.0.1:3141 >/dev/null 2>&1; do
    tries=$((tries + 1))
    if [ "$tries" -ge 30 ]; then
      echo "WARN: devpi did not become configurable; leaving default mirror settings" >&2
      return 0
    fi
    sleep 1
  done
  NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost devpi login root --password "" >/dev/null 2>&1 || true
  NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost devpi index root/pypi \
    mirror_url="${DEVPI_MIRROR_URL:-https://mirrors.ustc.edu.cn/pypi/simple/}" \
    mirror_web_url_fmt="${DEVPI_MIRROR_WEB_URL_FMT:-https://mirrors.ustc.edu.cn/pypi/web/simple/{name}/}" \
    mirror_ignore_serial_header=True >/dev/null 2>&1 || true
}

devpi-server --serverdir "$SERVERDIR" --host 0.0.0.0 --port 3141 --threads 50 &
DEVPI_PID=$!
configure_devpi_mirror &
wait "$DEVPI_PID"
