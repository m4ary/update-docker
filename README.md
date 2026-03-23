# dockupdater-portainer

Auto-update Docker containers through the Portainer API. Periodically pulls the latest images for all your containers and recreates them when a new version is available. Supports private registries configured in Portainer and notifications via [Shoutrrr](https://containrrr.dev/shoutrrr/).

## Quick Start

```yaml
# docker-compose.yml
services:
  updater:
    image: m4ary/dockupdater-portainer:latest
    container_name: dockupdater-portainer
    restart: unless-stopped
    environment:
      - PORTAINER_URL=http://your-portainer:9000
      - PORTAINER_TOKEN=your-api-token
      - PORTAINER_ENV_ID=1
      - UPDATE_INTERVAL=3600
      - SHOUTRRR_URL=
```

```bash
docker compose up -d
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PORTAINER_URL` | Yes | — | Portainer URL (e.g. `http://192.168.1.100:9000`) |
| `PORTAINER_TOKEN` | Yes | — | Portainer API token |
| `PORTAINER_ENV_ID` | No | `1` | Portainer environment ID |
| `UPDATE_INTERVAL` | No | `3600` | Seconds between scans |
| `SHOUTRRR_URL` | No | — | Shoutrrr notification URL |

## Getting a Portainer API Token

1. Log in to Portainer
2. Go to **My Account** (bottom-left)
3. Scroll to **Access Tokens**
4. Click **Add access token**

## Notifications

Uses [Shoutrrr](https://containrrr.dev/shoutrrr/) for notifications. Set `SHOUTRRR_URL` to any supported service:

```
telegram://token@telegram?channels=chatid
discord://token@id
slack://hook-url
gotify://host/token
```

For Telegram, use `channels=` (not `chats=`) in the query string.

### Notification Example

```
Updates applied:
  my-app: 1956d7c751dd -> 4498dcd55ee2
  redis: a1b2c3d4e5f6 -> f6e5d4c3b2a1
Scan complete: 12 containers, 2 updated, 9 up to date, 0 failed, 1 skipped
```

## How It Works

1. Fetches all registries from Portainer for authentication
2. Lists all containers in the environment
3. Pulls the latest image for each container (using registry credentials when needed)
4. Compares image IDs — if changed, recreates the container via Portainer
5. Sends a notification with the update summary

## Private Registries

Any registry configured in Portainer (GitLab, GitHub Container Registry, DigitalOcean, etc.) is automatically used for authentication when pulling images. No extra configuration needed.

## License

MIT
