FROM python:3.12-alpine

ARG VERSION=dev

LABEL org.opencontainers.image.title="dockupdater-portainer"
LABEL org.opencontainers.image.description="Auto-update Docker containers via Portainer API"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.source="https://github.com/m4ary/dockupdater-portainer"

RUN apk add --no-cache curl && \
    curl -sL https://github.com/containrrr/shoutrrr/releases/download/v0.8.0/shoutrrr_linux_amd64 -o /usr/local/bin/shoutrrr && \
    chmod +x /usr/local/bin/shoutrrr && \
    apk del curl

WORKDIR /app
COPY main.py .

CMD ["python3", "-u", "main.py"]
