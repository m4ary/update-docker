FROM python:3.12-alpine

ARG VERSION=dev
ARG TARGETARCH

LABEL org.opencontainers.image.title="dockupdater-portainer"
LABEL org.opencontainers.image.description="Auto-update Docker containers via Portainer API"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.source="https://github.com/m4ary/dockupdater-portainer"

RUN apk add --no-cache curl && \
    ARCH=$(case "${TARGETARCH}" in arm64) echo "arm64" ;; *) echo "amd64" ;; esac) && \
    curl -sL "https://github.com/containrrr/shoutrrr/releases/download/v0.8.0/shoutrrr_linux_${ARCH}" -o /usr/local/bin/shoutrrr && \
    chmod +x /usr/local/bin/shoutrrr && \
    apk del curl

WORKDIR /app
COPY main.py .

CMD ["python3", "-u", "main.py"]
