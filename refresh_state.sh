#!/usr/bin/env bash

CONTAINER_PREFIX="${CONTAINER_PREFIX:-agent-redteam-}"
docker ps -aq --filter "name=${CONTAINER_PREFIX}" | xargs -r docker rm -f -v
docker network ls --format '{{.Name}}' |  grep '^1_1_python_' |  xargs -r docker network rm
docker network ls --format '{{.Name}}' |  grep '^2_1_python_' |  xargs -r docker network rm
docker network ls --format '{{.Name}}' |  grep '^3_1_python_' |  xargs -r docker network rm

# Stop and remove all VMs in temp_vms
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TEMP_VMS_DIR="${TEMP_VMS_DIR:-${SCRIPT_DIR}/temp_vms}"

# If the first argument is vm, then we will stop and remove VMs, otherwise skip this step
if [ "$1" != "vm" ]; then
  echo "Skipping VM cleanup"
  exit 0
fi
if [ -d "$TEMP_VMS_DIR" ]; then
  for vm_folder in "$TEMP_VMS_DIR"/*; do
    if [ -d "$vm_folder" ]; then
      vm_name=$(basename "$vm_folder")
      vmx_file="$vm_folder/${vm_name}.vmx"
      
      if [ -f "$vmx_file" ]; then
        echo "Stopping VM: $vm_name"
        vmrun stop "$vmx_file" hard 
        sleep 2
      fi
    fi
  done
  
  # Remove all VM folders
  echo "Removing VM folders..."
  rm -rf "$TEMP_VMS_DIR"/*
  echo "All VMs stopped and folders removed"
else
  echo "temp_vms directory not found"
fi
