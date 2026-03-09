#!/bin/bash
set -e

# Load .env
set -a
source .env
set +a

VERSION=$(cat version.txt | tr -d '[:space:]')
IMAGE="${DOCKERHUB_USERNAME}/dockupdater-portainer"

echo "Logging in to Docker Hub..."
echo "${DOCKERHUB_PAT}" | docker login -u "${DOCKERHUB_USERNAME}" --password-stdin

# Create builder if needed
docker buildx inspect multiarch >/dev/null 2>&1 || \
    docker buildx create --name multiarch --use
docker buildx use multiarch

echo "Building and pushing ${IMAGE}:${VERSION} (amd64 + arm64)..."
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --build-arg VERSION="${VERSION}" \
    -t "${IMAGE}:${VERSION}" \
    -t "${IMAGE}:latest" \
    --push .

echo "Done! Pushed ${IMAGE}:${VERSION} (amd64 + arm64)"
