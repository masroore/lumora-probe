FROM python:3.13-slim

ARG UID=10001
ARG GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LUMORA_DATA_DIR=/var/lib/lumora \
    LUMORA_BIND_HOST=0.0.0.0 \
    LUMORA_ALLOW_UNAUTHENTICATED_NETWORK=true

WORKDIR /opt/lumora-probe

RUN groupadd --system --gid "${GID}" lumora \
    && useradd --system --uid "${UID}" --gid "${GID}" --home-dir /var/lib/lumora \
        --no-create-home --shell /usr/sbin/nologin lumora \
    && mkdir -p /var/lib/lumora \
    && chown -R "${UID}:${GID}" /var/lib/lumora

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY static ./static
COPY assets/vendor ./assets/vendor

RUN python -m pip install --no-cache-dir . \
    && rm -rf /root/.cache /opt/lumora-probe/src /opt/lumora-probe/assets

VOLUME ["/var/lib/lumora"]
EXPOSE 8000 11112

USER lumora

CMD ["lumora", "serve", "--trust-network", "--host", "0.0.0.0"]
