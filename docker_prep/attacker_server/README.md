# IPI Test Server

This container runs two Flask services:

- `8080`: serves the HTML test pages from the IPI dataset
- `8081`: simulates an attacker/C&C endpoint and collects request logs

## Prerequisites

Initialize the dataset submodules from the repository root first:

```bash
git submodule update --init --recursive
```

The build script reads from:

```text
data/ipi_web_dataset/html_pages
```

## Building the Image

From `./docker_prep/attacker_server`, build with:

```bash
./build_docker.sh
```

The script temporarily copies the dataset `html_pages` into the Docker build
context and produces the image:

```text
web-server:latest
```

## Standalone Usage

The framework uses a Docker network named `my-network`. Create it before
running manually (no error if it already exists):

```bash
docker network create my-network 2>/dev/null || true
docker rm -f ipi-test-server 2>/dev/null || true

docker run -d \
  --name ipi-test-server \
  --network my-network \
  -p 8084:8080 \
  -p 8085:8081 \
  web-server:latest
```

Check from the host:

```bash
curl http://localhost:8084/health  # HTML service
curl http://localhost:8085/health  # attacker service
```

Ports `8084`/`8085` are used on the host to match the framework's default port
mappings; inside the container the services still listen on `8080`/`8081`.

## Common Operations

List test pages:

```bash
curl http://localhost:8084/list | jq '.pages[] | .test_id' | head -10
```

Set the default test page:

```bash
HOST_IP="YOUR_HOST_IP"
curl "http://localhost:8084/set-default?test=ipi_cp_mip_001&attacker_server=http://${HOST_IP}:8085"
```

`HOST_IP` must be an address of the host machine reachable from the test
containers; fill it in according to your local Docker network setup, and do
not commit a specific machine's internal address.

Open the current test page:

```bash
curl http://localhost:8084/test
```

Inspect attacker-service status and logs:

```bash
curl http://localhost:8085/status
curl http://localhost:8085/logs | jq '.logs[-5:]'
```

View container logs or enter the container:

```bash
docker logs -f ipi-test-server
docker exec -it ipi-test-server bash
```

Stop and remove the container:

```bash
docker rm -f ipi-test-server
```

## Endpoint Overview

HTML service (`8080`):

- `GET /`: API description
- `GET /health`: health check
- `GET /test`: open the current default test page
- `GET /page?test=<id>`: open a specific test page
- `GET /list`: list test pages
- `GET /set-default?test=<id>`: set the default test page

Attacker service (`8081`):

- `GET/POST /collect`: collect exfiltrated data
- `GET/POST /exfil`: data-exfiltration endpoint
- `GET/POST /log`: log-collection endpoint
- `GET /status`: request statistics
- `GET /logs`: view request logs
- `GET /clear`: clear logs
- `GET /payload.sh`, `/payload.ps1`, `/backdoor.py`, etc.: serve test payloads

## Directory Layout

```text
attacker_server/
├── server.py       # both Flask services
├── Dockerfile
├── build_docker.sh
├── payloads/       # test payloads
└── README.md
```
