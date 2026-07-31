# Docker Deployment

Lumora Probe's image is a runtime package, not a development environment. Node is used
only when contributors rebuild committed frontend assets; the image installs and runs the
Python wheel with the already-committed `static/` and `assets/vendor/` files.

## Run

```console
docker build -t lumora-probe:local .
docker run --rm \
  --name lumora-probe \
  -p 127.0.0.1:8000:8000 \
  -p 127.0.0.1:11112:11112 \
  -v lumora-data:/var/lib/lumora \
  lumora-probe:local
```

The image exposes HTTP on port `8000` and DICOM on port `11112`. It uses one volume,
`/var/lib/lumora`, for the complete `LUMORA_DATA_DIR` tree. The container runs as the
non-root `lumora` user. Docker creates a named volume with ownership suitable for that
UID/GID; bind mounts must be writable by the image user or prepared with the image's
`UID`/`GID` build arguments.

The image sets `LUMORA_ALLOW_UNAUTHENTICATED_NETWORK=true` and starts with
`--trust-network --host 0.0.0.0` because a container must be reachable across its network
boundary. This is an explicit deployment acknowledgment, not authentication.

## Reverse-proxy boundary

The image does not add TLS, authentication, or RBAC. Put nginx, Caddy, or an equivalent
reverse proxy in front of the container when HTTP leaves a trusted local Docker network.
The reverse proxy is the security boundary. Keep the published ports loopback-bound unless
an external boundary is deliberately configured.

The DICOM port is likewise unauthenticated. Restrict it to the intended test network and
configure AE titles and routing outside the container according to the deployment topology.

See [deployment-topologies.md](deployment-topologies.md), [operator-guide.md](operator-guide.md),
and ADR-0010 / ADR-0011.
