#!/usr/bin/env python3
import urllib.request
import urllib.error
import urllib.parse
import json
import ssl
import base64
import os
import time
import subprocess

# Config from environment
PORTAINER = os.environ.get("PORTAINER_URL", "http://192.168.2.12:9001")
TOKEN = os.environ.get("PORTAINER_TOKEN", "")
ENV_ID = int(os.environ.get("PORTAINER_ENV_ID", "1"))
INTERVAL = int(os.environ.get("UPDATE_INTERVAL", "3600"))  # seconds
SHOUTRRR_URL = os.environ.get("SHOUTRRR_URL", "")  # e.g. telegram://token@telegram?channels=chatid
EXCLUDE_IMAGES = [s.strip().lower() for s in os.environ.get("EXCLUDE_IMAGES", "portainer/portainer-ce").split(",") if s.strip()]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def api(method, path, body=None, extra_headers=None):
    url = f"{PORTAINER}/api/endpoints/{ENV_ID}/docker{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"X-API-Key": TOKEN, "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=30) as res:
        raw = res.read()
        return json.loads(raw) if raw else {}


def portainer_api(method, path, body=None, timeout=30):
    url = f"{PORTAINER}/api{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                headers={"X-API-Key": TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as res:
        raw = res.read()
        return json.loads(raw) if raw else {}


def parse_image(image):
    """Parse image string into (registry, repo, tag). Returns None registry for Docker Hub."""
    tag = "latest"
    if ":" in image and not image.rsplit(":", 1)[-1].count("/"):
        image, tag = image.rsplit(":", 1)
    # Docker Hub: no dots in first segment (e.g. "nginx", "library/nginx", "user/repo")
    # Other registries: first segment has dots (e.g. "ghcr.io/user/repo")
    parts = image.split("/", 1)
    if "." in parts[0] or ":" in parts[0]:
        return parts[0], parts[1] if len(parts) > 1 else "", tag
    # Docker Hub
    if "/" not in image:
        return None, f"library/{image}", tag
    return None, image, tag


def get_dockerhub_remote_digest(repo, tag):
    """Get remote image digest from Docker Hub registry API (works for public images)."""
    # Get anonymous auth token
    token_url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull"
    req = urllib.request.Request(token_url)
    with urllib.request.urlopen(req, timeout=10) as res:
        token = json.loads(res.read())["token"]

    # Get manifest digest via HEAD request
    manifest_url = f"https://registry-1.docker.io/v2/{repo}/manifests/{tag}"
    req = urllib.request.Request(manifest_url, method="HEAD", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.docker.distribution.manifest.list.v2+json, "
                  "application/vnd.docker.distribution.manifest.v2+json, "
                  "application/vnd.oci.image.index.v1+json"
    })
    with urllib.request.urlopen(req, timeout=10) as res:
        return res.headers.get("Docker-Content-Digest", "")


def get_local_repo_digest(image):
    """Get the local image's repo digest from Portainer/Docker API."""
    encoded = urllib.parse.quote(image, safe="")
    data = api("GET", f"/images/{encoded}/json")
    for d in data.get("RepoDigests", []):
        # Format: "repo@sha256:abc..."
        if "@" in d:
            return d.split("@", 1)[1]
    return ""


def pull_image(image, registry_id=None):
    encoded = urllib.parse.quote(image, safe="")
    url = f"{PORTAINER}/api/endpoints/{ENV_ID}/docker/images/create?fromImage={encoded}"
    headers = {"X-API-Key": TOKEN}
    if registry_id:
        auth = base64.b64encode(json.dumps({"registryId": registry_id}).encode()).decode()
        headers["X-Registry-Auth"] = auth
    req = urllib.request.Request(url, data=b"", method="POST", headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=300) as res:
        output = res.read().decode()
    for line in output.strip().split("\n"):
        if line.strip():
            obj = json.loads(line)
            if "error" in obj:
                raise Exception(obj["error"])
    return output


def get_image_version(image_id):
    """Extract short digest as version identifier."""
    return image_id.replace("sha256:", "")[:12]


def notify(message):
    print(message)
    if not SHOUTRRR_URL:
        return
    try:
        result = subprocess.run(
            ["shoutrrr", "send", "-u", SHOUTRRR_URL, "-m", message],
            capture_output=True,
            text=True,
            timeout=15,
            check=False
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            print(f"  [notify error] shoutrrr exited with code {result.returncode}: {err}")
    except Exception as e:
        print(f"  [notify error] {e}")


def send_startup_notification():
    if not SHOUTRRR_URL:
        return
    notify("dockupdater-portainer started: notification test")


def run_update():
    # Load registries
    registries = portainer_api("GET", "/registries")
    registry_map = {}
    for r in registries:
        registry_map[r["URL"].lower()] = r["Id"]

    # List containers
    containers = api("GET", "/containers/json?all=true")
    print(f"Scanning {len(containers)} containers...")

    updated = []
    failed = []
    up_to_date = 0
    skipped = 0

    for i, c in enumerate(containers, 1):
        name = c["Names"][0].lstrip("/")
        image = c["Image"]
        old_image_id = c["ImageID"]

        # Resolve sha256 to tag
        if image.startswith("sha256:"):
            inspect = api("GET", f"/containers/{c['Id']}/json")
            image = inspect.get("Config", {}).get("Image", "")
            if not image or image.startswith("sha256:"):
                print(f"  [{i}/{len(containers)}] {name}: skipped (no tag)")
                skipped += 1
                continue

        # Skip excluded images (e.g. Portainer itself)
        if any(image.lower().startswith(exc) for exc in EXCLUDE_IMAGES):
            print(f"  [{i}/{len(containers)}] {name}: skipped (excluded)")
            skipped += 1
            continue

        print(f"  [{i}/{len(containers)}] {name}: checking {image}...")

        # Match registry
        registry_id = None
        image_lower = image.lower()
        for reg_url, reg_id in registry_map.items():
            if image_lower.startswith(reg_url):
                registry_id = reg_id
                break

        # For Docker Hub public images, check manifest digest first to avoid unnecessary pulls
        registry, repo, tag = parse_image(image)
        needs_pull = True
        if registry is None and registry_id is None:
            try:
                remote_digest = get_dockerhub_remote_digest(repo, tag)
                local_digest = get_local_repo_digest(image)
                if remote_digest and local_digest and remote_digest == local_digest:
                    print(f"    up to date (digest match)")
                    up_to_date += 1
                    needs_pull = False
                elif remote_digest:
                    print(f"    new version available, pulling...")
            except Exception:
                print(f"    manifest check failed, falling back to pull...")

        if not needs_pull:
            continue

        # Pull
        try:
            pull_image(image, registry_id)
        except Exception as e:
            print(f"    pull failed: {e}")
            failed.append(name)
            continue

        # Compare
        encoded_img = urllib.parse.quote(image, safe="")
        new_image_data = api("GET", f"/images/{encoded_img}/json")
        new_image_id = new_image_data.get("Id", "")

        if old_image_id == new_image_id:
            up_to_date += 1
            continue

        old_ver = get_image_version(old_image_id)
        new_ver = get_image_version(new_image_id)

        # Recreate
        try:
            print(f"    recreating {name}...")
            portainer_api("POST", f"/docker/{ENV_ID}/containers/{c['Id']}/recreate",
                          {"PullImage": False}, timeout=120)
            updated.append(f"{name}: {old_ver} -> {new_ver}")
        except Exception as e:
            print(f"    recreate failed: {e}")
            failed.append(name)

    # Build notification
    lines = []
    if updated:
        lines.append("Updates applied:")
        for u in updated:
            lines.append(f"  {u}")
    if failed:
        lines.append(f"Failed: {', '.join(failed)}")

    summary = f"Scan complete: {len(containers)} containers, {len(updated)} updated, {up_to_date} up to date, {len(failed)} failed, {skipped} skipped"
    lines.append(summary)

    message = "\n".join(lines)

    if updated or failed:
        notify(message)
    else:
        print(summary)


if __name__ == "__main__":
    print(f"Portainer Image Updater")
    print(f"  URL: {PORTAINER}")
    print(f"  Env: {ENV_ID}")
    print(f"  Interval: {INTERVAL}s")
    print(f"  Exclude: {', '.join(EXCLUDE_IMAGES) if EXCLUDE_IMAGES else 'none'}")
    print(f"  Notify: {'yes' if SHOUTRRR_URL else 'no'}")
    print()
    send_startup_notification()
    print()

    while True:
        try:
            run_update()
        except Exception as e:
            print(f"Error during update: {e}")
        print(f"\nNext scan in {INTERVAL}s...\n")
        time.sleep(INTERVAL)
