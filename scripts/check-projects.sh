#!/bin/bash
# Check compose project labels for all running containers
for id in $(docker ps -q); do
  name=$(docker inspect --format '{{.Name}}' "$id" | sed 's/^\///')
  project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$id")
  echo "$name -> $project"
done | sort
