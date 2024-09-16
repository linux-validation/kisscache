#!/bin/bash

# Helper function for logging
log() {
    echo "[INFO] $1"
}

# Usage function to display instructions
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "This script sets up an LXC container in Proxmox, installs Docker and Docker Compose, and runs the KissCache service."
    echo ""
    echo "Available environment variables:"
    echo "  CONTAINER_ID    : LXC Container ID (default: 110)"
    echo "  HOSTNAME        : Hostname for the LXC container (default: kisscache-lxc)"
    echo "  TEMPLATE        : LXC container template (default: local:vztmpl/debian-11-standard_11.7-1_amd64.tar.zst)"
    echo "  STORAGE         : Proxmox storage pool (default: local-zfs)"
    echo "  PASSWORD        : Root password for the LXC container (default: yourpassword)"
    echo "  CPU_CORES       : Number of CPU cores for the container (default: 2)"
    echo "  MEMORY          : Memory allocation in MB (default: 2048)"
    echo "  NETWORK_BRIDGE  : Network bridge (default: vmbr0)"
    echo "  GIT_REPO        : Git repository URL for KissCache (default: https://gitlab.com/Linaro/kisscache.git)"
    echo "  BRANCH          : Git branch to clone (default: main)"
    echo "  IP_ADDRESS      : Static IP address for the container (optional)"
    echo "  GATEWAY         : Gateway for the static IP address (optional)"
    echo ""
    echo "Options:"
    echo "  --help          : Display this usage message."
    echo ""
    echo "Example Usage:"
    echo "  CONTAINER_ID=120 IP_ADDRESS=192.168.1.100/24 GATEWAY=192.168.1.1 ./script.sh"
    echo ""
    exit 0
}

# Check for the --help flag and display usage if present
if [[ "$1" == "--help" ]]; then
    usage
fi

# Set default values for environment variables
CONTAINER_ID=${CONTAINER_ID:-110}           # LXC Container ID (default: 110)
HOSTNAME=${HOSTNAME:-"kisscache-lxc"}       # LXC Hostname (default: kisscache-lxc)
TEMPLATE=${TEMPLATE:-"local:vztmpl/debian-11-standard_11.7-1_amd64.tar.zst"} # Debian template path
STORAGE=${STORAGE:-"local-zfs"}             # Storage pool (default: local-zfs)
PASSWORD=${PASSWORD:-"yourpassword"}        # Root password for LXC
CPU_CORES=${CPU_CORES:-2}                   # Number of CPU cores (default: 2)
MEMORY=${MEMORY:-2048}                      # Memory in MB (default: 2048)
NETWORK_BRIDGE=${NETWORK_BRIDGE:-"vmbr0"}   # Network bridge (default: vmbr0)
GIT_REPO=${GIT_REPO:-"https://gitlab.com/Linaro/kisscache.git"}  # Git repo for KissCache
BRANCH=${BRANCH:-"master"}                    # Git branch (default: master)
IP_ADDRESS=${IP_ADDRESS:-""}                # IP address (optional)
GATEWAY=${GATEWAY:-""}                      # Gateway (optional)

# Step 1: Check for necessary dependencies
check_dependencies() {
    log "Checking dependencies..."
    if ! command -v pct &>/dev/null; then
        log "Error: pct command not found. Please ensure you are running this script on a Proxmox system."
        exit 1
    fi
}

# Step 2: Stop and destroy the existing container (if it exists)
destroy_container() {
    if pct status $CONTAINER_ID &>/dev/null; then
        log "Stopping and destroying existing container with ID $CONTAINER_ID..."
        pct stop $CONTAINER_ID
        pct destroy $CONTAINER_ID
    fi
}

# Step 3: Create the LXC container with nesting enabled and proper DHCP configuration
create_container() {
    log "Creating LXC container with ID $CONTAINER_ID..."

    if [[ -n "$IP_ADDRESS" && -n "$GATEWAY" ]]; then
        log "Creating container with static IP: $IP_ADDRESS and Gateway: $GATEWAY..."
        pct create $CONTAINER_ID $TEMPLATE \
            --hostname $HOSTNAME \
            --storage $STORAGE \
            --rootfs 8 \
            --cores $CPU_CORES \
            --memory $MEMORY \
            --net0 name=eth0,bridge=$NETWORK_BRIDGE,ip=$IP_ADDRESS,gw=$GATEWAY \
            --password $PASSWORD \
            --unprivileged 1 \
            --features nesting=1
    else
        log "Creating container with DHCP configuration..."
        pct create $CONTAINER_ID $TEMPLATE \
            --hostname $HOSTNAME \
            --storage $STORAGE \
            --rootfs 8 \
            --cores $CPU_CORES \
            --memory $MEMORY \
            --net0 name=eth0,bridge=$NETWORK_BRIDGE,ip=dhcp \
            --password $PASSWORD \
            --unprivileged 1 \
            --features nesting=1
    fi
}

# Step 4: Modify the LXC configuration to enable Docker support
modify_lxc_config() {
    log "Modifying LXC configuration for Docker support..."
    echo -e "lxc.apparmor.profile: unconfined\nlxc.cap.drop:\nlxc.mount.auto: proc:rw sys:rw\nfeatures: nesting=1" >> /etc/pve/lxc/$CONTAINER_ID.conf
}

# Step 5: Start the LXC container
start_container() {
    log "Starting the LXC container..."
    pct start $CONTAINER_ID
}

# Step 6: Install Docker and Docker Compose inside the container
install_docker() {
    log "Installing Docker and Docker Compose inside the container..."
    pct exec $CONTAINER_ID -- bash -c "apt update && apt install -y apt-transport-https ca-certificates curl gnupg2 git software-properties-common && \
        curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add - && \
        echo \"deb [arch=amd64] https://download.docker.com/linux/debian bullseye stable\" > /etc/apt/sources.list.d/docker.list && \
        apt update && apt install -y docker-ce=5:20.10.17~3-0~debian-bullseye docker-ce-cli=5:20.10.17~3-0~debian-bullseye containerd.io && \
        curl -L \"https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/local/bin/docker-compose && \
        chmod +x /usr/local/bin/docker-compose && ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose"
}

# Step 7: Clone the Git repository and bring up Docker Compose
setup_kisscache() {
    log "Cloning the KissCache repository from $GIT_REPO..."
    pct exec $CONTAINER_ID -- bash -c "git clone -b $BRANCH $GIT_REPO /app/kisscache"
    
    log "Starting Docker Compose services from the cloned repository..."
    pct exec $CONTAINER_ID -- bash -c "cd /app/kisscache && docker-compose up -d"
}

# Main execution flow
check_dependencies
destroy_container
create_container
modify_lxc_config
start_container
install_docker
setup_kisscache

log "LXC container $CONTAINER_ID has been set up with Docker Compose for KissCache from $GIT_REPO."
