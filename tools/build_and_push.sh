#!/bin/sh
# Builds the Script-Server image from this checkout and pushes it to the private registry.
#
#   tools/build_and_push.sh v3                 # -> 192.168.102.227:5011/script-server:v3
#   tools/build_and_push.sh 3.0.0              # a version tag, kept alongside
#
# Script Server 3 (version.txt 3.x) is built from this branch; Script Server 2 images are the
# v2 / 2.x tags already in the registry. A tag whose major version doesn't match version.txt
# (e.g. v2 from a 3.x checkout) is refused, so a v3 build can't replace the v2 install's image.
#   tools/build_and_push.sh latest --allow-latest
#   REGISTRY=myhost:5000 tools/build_and_push.sh v2
#
# Run it from anywhere inside the checkout (it builds from the repo root). Refuses "latest" unless
# --allow-latest is given: "latest" is what an existing (v1) install pulls, so pushing a test build
# there replaces it the next time that install updates.
#
# Pushing to a plain-HTTP registry needs it listed under "insecure-registries" in the Docker daemon
# config of the machine doing the push (a QNAP already pulling from it has that). Build on the NAS
# itself, or on another x86_64 machine - an Apple Silicon Mac needs
#   docker buildx build --platform linux/amd64 ... --push
# instead of the plain build below.

set -e

REGISTRY="${REGISTRY:-192.168.102.227:5011}"
IMAGE="${IMAGE:-script-server}"
TAG="$1"
ALLOW_LATEST=false
[ "$2" = "--allow-latest" ] && ALLOW_LATEST=true

if [ -z "$TAG" ]; then
    echo "Usage: $0 <tag> [--allow-latest]   e.g. $0 v3" >&2
    exit 1
fi
if [ "$TAG" = latest ] && [ "$ALLOW_LATEST" != true ]; then
    echo "Refusing to push :latest - that's what the existing install pulls." >&2
    echo "Use a tag like v3, or pass --allow-latest when you really are switching over." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="$(cat version.txt 2>/dev/null || echo unknown)"
MAJOR="${VERSION%%.*}"
case "$TAG" in
    v[0-9]* | [0-9]*)
        TAG_MAJOR="$(echo "${TAG#v}" | cut -d. -f1)"
        if [ "$TAG_MAJOR" != "$MAJOR" ]; then
            echo "Refusing to push :$TAG from a $VERSION checkout - that tag belongs to Script Server $TAG_MAJOR." >&2
            echo "Use v$MAJOR or $VERSION, or check out the Script Server $TAG_MAJOR source." >&2
            exit 1
        fi
        ;;
esac
REF="$REGISTRY/$IMAGE:$TAG"

echo "Building $REF (Script-Server $VERSION, $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?') @ $(git rev-parse --short HEAD 2>/dev/null || echo '?'))"
docker build -f tools/Dockerfile -t "$REF" .

echo "Pushing $REF"
docker push "$REF"

echo
echo "Done. Tags now in the registry for $IMAGE:"
if command -v curl >/dev/null 2>&1; then
    curl -fsS "http://$REGISTRY/v2/$IMAGE/tags/list" || echo "(could not list tags - check http://$REGISTRY/v2/$IMAGE/tags/list)"
    echo
fi
echo "On the NAS, from the compose folder:  docker compose pull && docker compose up -d"
