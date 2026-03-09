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
    with urllib.request.urlopen(req, context=ctx) as res:
        raw = res.read()
        return json.loads(raw) if raw else {}


def portainer_api(method, path, body=None):
    url = f"{PORTAINER}/api{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                headers={"X-API-Key": TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=ctx) as res:
        raw = res.read()
        return json.loads(raw) if raw else {}


def pull_image(image, registry_id=None):
    encoded = urllib.parse.quote(image, safe="")
    url = f"{PORTAINER}/api/endpoints/{ENV_ID}/docker/images/create?fromImage={encoded}"
    headers = {"X-API-Key": TOKEN}
    if registry_id:
        auth = base64.b64encode(json.dumps({"registryId": registry_id}).encode()).decode()
        headers["X-Registry-Auth"] = auth
    req = urllib.request.Request(url, data=b"", method="POST", headers=headers)
    with urllib.request.urlopen(req, context=ctx) as res:
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
        subprocess.run(["shoutrrr", "send", "-u", SHOUTRRR_URL, "-m", message],
                       capture_output=True, timeout=15)
    except Exception as e:
        print(f"  [notify error] {e}")


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

    for c in containers:
        name = c["Names"][0].lstrip("/")
        image = c["Image"]
        old_image_id = c["ImageID"]

        # Resolve sha256 to tag
        if image.startswith("sha256:"):
            inspect = api("GET", f"/containers/{c['Id']}/json")
            image = inspect.get("Config", {}).get("Image", "")
            if not image or image.startswith("sha256:"):
                skipped += 1
                continue

        # Match registry
        registry_id = None
        image_lower = image.lower()
        for reg_url, reg_id in registry_map.items():
            if image_lower.startswith(reg_url):
                registry_id = reg_id
                break

        # Pull
        try:
            pull_image(image, registry_id)
        except Exception:
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
            portainer_api("POST", f"/docker/{ENV_ID}/containers/{c['Id']}/recreate",
                          {"PullImage": False})
            updated.append(f"{name}: {old_ver} -> {new_ver}")
        except Exception:
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
    print(f"  Notify: {'yes' if SHOUTRRR_URL else 'no'}")
    print()

    while True:
        try:
            run_update()
        except Exception as e:
            print(f"Error during update: {e}")
        print(f"\nNext scan in {INTERVAL}s...\n")
        time.sleep(INTERVAL)
