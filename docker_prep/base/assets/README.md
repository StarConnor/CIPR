# Base image build assets

Place the local inputs required by the base images in this directory:

- `node-v22.21.1-linux-x64.tar.gz`
- `automation_server/` (copied from `automation_server_appium/automation_server`)
- `mitm-certs/mitmproxy-ca.pem`
- `mitm-certs/mitmproxy-ca-cert.pem`
- `id_ed25519_1.pub` (or set `PUBLIC_KEY_FILE`)

The automation server source is kept visible for review. Credentials and the
rest of the external automation project are intentionally not copied here.
Other files in this directory are local build inputs and are ignored by Git.
