#!/usr/bin/env bash
set -euo pipefail

mkdir -p \
  /cache/apt-cacher-ng \
  /cache/verdaccio/storage \
  /cache/verdaccio/plugins \
  /cache/devpi \
  /cache/nginx/maven \
  /cache/nginx/go \
  /cache/nginx/cargo \
  /cache/nginx/rubygems \
  /cache/nginx/packagist

# apt-cacher-ng in Debian can still use its compiled/default cache path in some setups.
# Keep the persistent cache volume authoritative by linking the default path into /cache.
rm -rf /var/cache/apt-cacher-ng
ln -s /cache/apt-cacher-ng /var/cache/apt-cacher-ng

# apt-cacher-ng is configured by file, not env.
cat >/etc/apt-cacher-ng/acng.conf <<'ACNG'
CacheDir: /cache/apt-cacher-ng
LogDir: /var/log/apt-cacher-ng
Port: 3142
BindAddress: 0.0.0.0
Remap-debrep: file:deb_mirrors.gz /debian ; file:ubuntu_mirrors /ubuntu
ExThreshold: 0
ACNG

exec "$@"
