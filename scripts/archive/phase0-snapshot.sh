#!/bin/bash
set -e

echo "=== PHASE 0: Creating emergency rollback snapshot ==="

mkdir -p ~/backup/docker_state

# Snapshot all container configs
docker inspect $(docker ps -aq) > ~/backup/docker_state/containers.json 2>&1
echo "✓ Containers snapshot saved"

# Snapshot all networks
docker network inspect $(docker network ls -q) > ~/backup/docker_state/networks.json 2>&1
echo "✓ Networks snapshot saved"

# Snapshot all volumes
docker volume inspect $(docker volume ls -q) > ~/backup/docker_state/volumes.json 2>&1
echo "✓ Volumes snapshot saved"

# Snapshot image list
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}' > ~/backup/docker_state/images.txt
echo "✓ Images list saved"

# Snapshot compose project labels
docker ps --format '{{.Names}} {{.Label "com.docker.compose.project"}}' > ~/backup/docker_state/compose-labels.txt
echo "✓ Compose labels saved"

# Show file sizes
echo ""
echo "=== Snapshot files ==="
ls -lh ~/backup/docker_state/
echo ""
echo "=== PHASE 0 COMPLETE ==="
