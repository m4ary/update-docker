#!/bin/bash
set -e

# Load .env
set -a
source .env
set +a

VERSION=$(cat version.txt | tr -d '[:space:]')
IMAGE="${DOCKERHUB_USERNAME}/dockupdater-portainer"

echo "Building ${IMAGE}:${VERSION}..."
docker build --build-arg VERSION="${VERSION}" -t "${IMAGE}:${VERSION}" -t "${IMAGE}:latest" .

echo "Logging in to Docker Hub..."
echo "${DOCKERHUB_PAT}" | docker login -u "${DOCKERHUB_USERNAME}" --password-stdin

echo "Pushing ${IMAGE}:${VERSION} and latest..."
docker push "${IMAGE}:${VERSION}"
docker push "${IMAGE}:latest"

echo "Done! Pushed ${IMAGE}:${VERSION}"
