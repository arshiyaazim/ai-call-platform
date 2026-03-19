#!/bin/bash
docker ps --format "{{.Names}} project={{.Label \"com.docker.compose.project\"}}" | sort
