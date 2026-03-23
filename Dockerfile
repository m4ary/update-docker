FROM python:3.12-alpine

ARG VERSION=dev
ARG TARGETARCH

LABEL org.opencontainers.image.title="dockupdater-portainer"
LABEL org.opencontainers.image.description="Auto-update Docker containers via Portainer API"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.source="https://github.com/m4ary/dockupdater-portainer"

RUN apk add --no-cache curl tar && \
    ARCH=$(case "${TARGETARCH}" in arm64) echo "arm64" ;; *) echo "amd64" ;; esac) && \
    curl -fsSL "https://github.com/containrrr/shoutrrr/releases/download/v0.8.0/shoutrrr_linux_${ARCH}.tar.gz" -o /tmp/shoutrrr.tar.gz && \
    tar -xzf /tmp/shoutrrr.tar.gz -C /tmp shoutrrr && \
    mv /tmp/shoutrrr /usr/local/bin/shoutrrr && \
    chmod +x /usr/local/bin/shoutrrr && \
    rm -f /tmp/shoutrrr.tar.gz && \
    apk del curl tar

WORKDIR /app
COPY main.py .

CMD ["python3", "-u", "main.py"]
