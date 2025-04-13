#!/usr/bin/env sh
# SHA256: c2e0adde5687e83104a7292c9e7610267c6660daeca8732bb2dc8da3a0e1d109
# shellcheck disable=SC2129,SC1091,SC1090,SC2086
#
# example direct usage from git:
# DOMAIN_NAME=example.com sh -c "$(curl -fsSL https://raw.githubusercontent.com/waldiez/runner/refs/heads/main/deploy/compose/do.sh)"
#
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    cat <<EOF
Usage: $0 --domain-name example.com [--certbot-email email@example.com] [--skip-certbot]

Options:
  --domain-name       (required) Domain name for the runner (e.g., example.com)
  --certbot-email     Email to use with Certbot (optional but recommended)
  --skip-certbot      Skip domain reachability check and SSL certificate issuance (useful for testing)
  --help              Show this help message and exit

You can also pre-set:
  DOMAIN_NAME, CERTBOT_EMAIL, SKIP_CERTBOT as environment variables.

Example:
  DOMAIN_NAME=example.com SKIP_CERTBOT=1 ./do.sh
EOF
    exit 0
fi
set -e
SCRIPT_URL="https://raw.githubusercontent.com/waldiez/runner/refs/heads/main/deploy/compose/do.sh"
###################################################################################################
# Check if the script is being run from a terminal or streamed
###################################################################################################
if [ -z "$_WALDIEZ_DO_SH_RELOADED" ]; then
    if ! [ -f "$0" ] || ! [ -s "$0" ]; then
        if ! command -v curl >/dev/null 2>&1; then
            echo "'curl' is required but not installed. Please install it and re-run the script."
            exit 1
        fi
        # Pick a safe directory to save the downloaded script
        _SAFE_DIR="${HOME:-$(pwd -P)}"
        [ -w "$_SAFE_DIR" ] || _SAFE_DIR="$(pwd -P)"
        [ -w "$_SAFE_DIR" ] || _SAFE_DIR="/tmp"
        _TMP_SCRIPT="${_SAFE_DIR}/do.sh"
        echo "Script is being streamed or piped. Downloading to $_TMP_SCRIPT for proper execution..."
        curl -fsSL "${SCRIPT_URL}" -o "$_TMP_SCRIPT" || {
            echo "Failed to download the script. Exiting."
            exit 1
        }
        _EXPECTED_HASH="$(awk '/^# SHA256:/ { print $3 }' "$_TMP_SCRIPT")"
        _DOWNLOADED_HASH="$(awk '!/^# SHA256:/ { print }' "$_TMP_SCRIPT" | sha256sum | awk '{print $1}')"
        if [ "${_DOWNLOADED_HASH}" != "${_EXPECTED_HASH}" ]; then
            echo "Checksum verification failed!"
            echo "Expected: ${_EXPECTED_HASH}"
            echo "Actual:   ${_DOWNLOADED_HASH}"
            exit 1
        fi
        chmod +x "$_TMP_SCRIPT"
        export _WALDIEZ_DO_SH_RELOADED=1
        exec "$_TMP_SCRIPT" "$@"
    fi
fi
#
##################################################################################################
# Constants and Env Setup
##################################################################################################
_SCRIPT_PATH="$(readlink -f "$0")"
_MY_DIR="$(dirname "$_SCRIPT_PATH")"
cd "$_MY_DIR" || exit 1
#
_ENV_FILE_NAME="waldiez_runner_env.sh"
_ENV_FILE="$_MY_DIR/$_ENV_FILE_NAME"
#
if [ -f "$_ENV_FILE" ]; then
    . "$_ENV_FILE"
fi
#
# non-interactive mode
export DEBIAN_FRONTEND=noninteractive
# Parse CLI arguments
DOMAIN_NAME="${DOMAIN_NAME:-}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
SKIP_CERTBOT="${SKIP_CERTBOT:-0}"  # to be easier to test this script
#
while [ $# -gt 0 ]; do
    case "$1" in
        --domain-name)
            DOMAIN_NAME="$2"; shift 2;;
        --certbot-email)
            CERTBOT_EMAIL="$2"; shift 2;;
        --skip-certbot)
            SKIP_CERTBOT=1; shift;;
        *)
            echo "Unknown argument: $1"; exit 1;;
    esac
done

if [ -z "$DOMAIN_NAME" ]; then
    echo "Error: DOMAIN_NAME is required."
    echo "Use --domain-name example.com or set DOMAIN_NAME in the environment."
    exit 1
fi

cat > "${_ENV_FILE}" <<EOF
DOMAIN_NAME="${DOMAIN_NAME}"
CERTBOT_EMAIL="${CERTBOT_EMAIL}"
SKIP_CERTBOT="${SKIP_CERTBOT}"
CONTAINER_COMMAND="docker"
EOF
# once more with the current values
. "$_ENV_FILE"
##################################################################################################
# OS Detection
##################################################################################################
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID=$(printf "%s" "$ID" | tr '[:upper:]' '[:lower:]')
        OS_NAME="${PRETTY_NAME}"
    elif [ -f /etc/lsb-release ]; then
        . /etc/lsb-release
        OS_ID="$(printf "%s" "${DISTRIB_ID}" | tr '[:upper:]' '[:lower:]')"
        OS_NAME="${DISTRIB_DESCRIPTION}"
    else
        echo "Could not detect OS."
        exit 1
    fi
    echo "Detected OS: ${OS_NAME} (${OS_ID})"
}

detect_os
##################################################################################################
# Package Installation Abstraction
##################################################################################################
do_install() {
    packages="$*"
    case "$OS_ID" in
        ubuntu|debian)
            sudo apt update
            sudo apt install -y ${packages}
            ;;
        centos|rhel|rocky|fedora)
            sudo dnf install -y $packages || sudo yum install -y ${packages}
            ;;
        *)
            echo "Unsupported OS: ${OS_ID}"
            exit 1
            ;;
    esac
}
do_upgrade() {
    case "$OS_ID" in
        ubuntu|debian)
            sudo apt update && sudo apt dist-upgrade -y
            ;;
        centos|rhel|rocky|fedora)
            if [ "${OS_ID}" != "fedora" ]; then
                if [ "${OS_ID}" = "rhel" ]; then
                    OS_VERSION_ID="$(. /etc/os-release && echo "$VERSION_ID" | cut -d. -f1)"
                else
                    OS_VERSION_ID="9"
                fi
                EPEL_RPM_URL="https://dl.fedoraproject.org/pub/epel/epel-release-latest-${OS_VERSION_ID}.noarch.rpm"
                echo "Installing EPEL release from ${EPEL_RPM_URL}..."
                sudo dnf install -y "$EPEL_RPM_URL" --skip-broken || sudo yum install -y "$EPEL_RPM_URL" --skip-broken
                sudo dnf install -y epel-release
            fi
            sudo dnf upgrade -y || sudo yum upgrade -y
            sudo dnf clean all
            ;;
        *)
            echo "Unsupported OS: ${OS_ID}"
            exit 1
            ;;
    esac
}
##################################################################################################
# Ensure User With Sudo
##################################################################################################
# first let's make sure that sudo exists as command
if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo not found. Installing..."
    case "$OS_ID" in
        ubuntu|debian) apt update && apt install -y sudo ;;
        centos|rhel|rocky|fedora) yum install -y sudo || dnf install -y sudo ;;
    esac
fi
get_sudo_group() {
    case "$OS_ID" in
        ubuntu|debian) echo "sudo" ;;
        rhel|centos|rocky|fedora) echo "wheel" ;;
        *) echo "sudo" ;;  # fallback
    esac
}
SUDO_GROUP="$(get_sudo_group)"
# Find first sudo-capable user
get_sudo_user() {
    SUDO_GROUP=$(get_sudo_group)
    USER_FROM_GROUP=$(getent group "$SUDO_GROUP" | cut -d: -f4 | tr ',' '\n' | grep -Ev '^\s*$' | head -n 1)

    if [ -n "$USER_FROM_GROUP" ]; then
        echo "$USER_FROM_GROUP"
        return
    fi
    # Fallback to checking sudo privileges
    # shellcheck disable=SC2013
    for user in $(awk -F: '{ if ($3 >= 1000 && $1 != "nobody") print $1 }' /etc/passwd); do
        if sudo -n -l -U "$user" 2>/dev/null | grep -q 'NOPASSWD: ALL'; then
            echo "$user"
            return
        fi
    done
}
# Find unused GID
find_group_id() {
    try_first=1000
    try_last=60000
    while [ "${try_first}" -lt "${try_last}" ]; do
        if ! getent group "${try_first}" > /dev/null 2>&1; then
            echo "${try_first}"
            return
        fi
        try_first=$((try_first + 1))
    done
    echo "No available group ID found in range"
    exit 1
}
# Prefer to use the same UID as GID if available, otherwise find a free one
find_user_id() {
    group_id="$1"
    if [ -z "$group_id" ]; then
        echo "No group ID provided"
        exit 1
    fi
    # First, check if the GID is unused as a UID
    if ! getent passwd "$group_id" >/dev/null 2>&1; then
        echo "$group_id"
        return
    fi
    # Otherwise, find a new UID
    try_uid=1000
    while [ "$try_uid" -lt 60000 ]; do
        if ! getent passwd "$try_uid" >/dev/null 2>&1; then
            echo "$try_uid"
            return
        fi
        try_uid=$((try_uid + 1))
    done
    echo "No available UID found"
    exit 1
}
# switch if needed to non-root user
if [ "$(id -u)" -eq 0 ]; then
    SUDO_USER="$(get_sudo_user)"

    if [ -n "${SUDO_USER}" ]; then
        echo "Found sudo user: ${SUDO_USER}"
        # the user should also have password-less sudo:
        if ! sudo -l -U "${SUDO_USER}" | grep -q 'NOPASSWD: ALL'; then
            echo "User ${SUDO_USER} does not have password-less sudo. Exiting."
            echo "${SUDO_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-${SUDO_USER}"
            chmod 0440 "/etc/sudoers.d/90-${SUDO_USER}"
        fi
    else
        echo "No sudo user found. Creating one..."
        user_name_and_group="waldiez"
        group_id="$(find_group_id)"
        user_id="$(find_user_id "${group_id}")"

        echo "Creating group '${user_name_and_group}' (GID ${group_id})..."
        if command -v addgroup >/dev/null 2>&1; then
            addgroup --gid "${group_id}" "${user_name_and_group}"
        else
            groupadd -g "${group_id}" "${user_name_and_group}"
        fi
        echo "Creating user '${user_name_and_group}' (UID ${user_id})..."
        if command -v adduser >/dev/null 2>&1 && adduser --help 2>&1 | grep -q -- '--disabled-password'; then
            adduser --disabled-password --gecos '' --shell /bin/bash \
                        --uid "${user_id}" --gid "${group_id}" "${user_name_and_group}"
        else
            useradd -m -u "${user_id}" -g "${group_id}" -s /bin/bash "${user_name_and_group}"
            passwd -l "${user_name_and_group}"  # Lock password (disable login)
        fi
        echo "Adding user to sudo group..."
        usermod -aG "${SUDO_GROUP}" "${user_name_and_group}"
        echo "${user_name_and_group} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-${user_name_and_group}"
        chmod 0440 "/etc/sudoers.d/90-${user_name_and_group}"
        SUDO_USER="${user_name_and_group}"
    fi
    # Copy root's authorized_keys to user ONLY if theirs is missing
    USER_HOME=$(getent passwd "${SUDO_USER}" | cut -d: -f6)
    USER_AUTH_KEYS="${USER_HOME}/.ssh/authorized_keys"
    ROOT_AUTH_KEYS="/root/.ssh/authorized_keys"

    if [ -f "${ROOT_AUTH_KEYS}" ]; then
        mkdir -p "${USER_HOME}/.ssh"
        touch "${USER_AUTH_KEYS}"
        if ! grep -q -F -f "${ROOT_AUTH_KEYS}" "${USER_AUTH_KEYS}"; then
            echo "Appending missing keys from root to $SUDO_USER..."
            cat "$ROOT_AUTH_KEYS" >> "${USER_AUTH_KEYS}"
            sort -u "${USER_AUTH_KEYS}" -o "${USER_AUTH_KEYS}"
            chown -R "${SUDO_USER}:${SUDO_USER}" "${USER_HOME}/.ssh"
            chmod 700 "${USER_HOME}/.ssh"
            chmod 600 "${USER_AUTH_KEYS}"
        fi
    fi
    echo "Re-running script as user: ${SUDO_USER}"
    # Let's avoid any permission issues if "$_SCRIPT_PATH" is in a restricted location
    SCRIPT_COPY="${USER_HOME}/$(basename "$_SCRIPT_PATH")"
    _src="$(readlink -f "${_SCRIPT_PATH}")"
    _dst="$(readlink -f "${SCRIPT_COPY}")"
    if [ "$_src" != "$_dst" ]; then
        # Copy the script to the user's home directory
        echo "Copying script to ${SCRIPT_COPY}..."
        mkdir -p "${USER_HOME}"
        cp "${_src}" "${_dst}"
        rm "${_src}" 2>/dev/null || true
    fi
    chown "${SUDO_USER}:${SUDO_USER}" "${SCRIPT_COPY}"
    chmod +rx "${SCRIPT_COPY}"
    # let's also pass the env file (if not the same
    _src="$(readlink -f "${_ENV_FILE}")"
    _dst="${USER_HOME}/${_ENV_FILE_NAME}"
    if [ "$_src" != "$_dst" ]; then
        cp "${_src}" "${_dst}"
        rm "${_src}" 2>/dev/null || true
    fi
    chown "${SUDO_USER}:${SUDO_USER}" "${USER_HOME}/${_ENV_FILE_NAME}" 2>/dev/null || true

    exec sudo -u "${SUDO_USER}" sh "${SCRIPT_COPY}"
fi
##################################################################################################
# If we are here, we are not root
# continue as the sudo user
echo "Running as user: $(whoami)"
do_upgrade
#
##################################################################################################
# Base Packages
##################################################################################################
do_install make curl git ca-certificates python3
case "$OS_ID" in
    ubuntu|debian)
        do_install python-is-python3
        ;;
    centos|fedora|rhel|rocky)
        do_install python-unversioned-command
        ;;
esac
##################################################################################################
#
##################################################################################################
# Docker
##################################################################################################
install_docker_deb_family() {
    # https://docs.docker.com/engine/install/ubuntu/
    # https://docs.docker.com/engine/install/debian/
    do_install ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL "https://download.docker.com/linux/${OS_ID}/gpg" -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    # Add the repository to Apt sources:
    codename="$(. /etc/os-release && echo "${UBUNTU_CODENAME:-${VERSION_CODENAME}}")"
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${OS_ID} \
    $codename stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt update
    do_install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}
install_docker_rpm_family() {
    # https://docs.docker.com/engine/install/centos/
    # https://docs.docker.com/engine/install/fedora/
    # https://docs.docker.com/engine/install/rhel/
    # https://docs.rockylinux.org/gemstones/containers/docker/
    do_install dnf-plugins-core
    repo_id="${OS_ID}"
    if [ "$OS_ID" = "rocky" ]; then
        repo_id="rhel"
    fi
    # let's try to avoid:
    # Unknown argument "--add-repo" for command "config-manager". Add "--help" for more information about the arguments.
    if command -v dnf-3 >/dev/null 2>&1; then
        sudo dnf-3 config-manager --add-repo "https://download.docker.com/linux/${repo_id}/docker-ce.repo"
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf config-manager --add-repo "https://download.docker.com/linux/${repo_id}/docker-ce.repo"
    elif command -v yum >/dev/null 2>&1; then
        sudo yum-config-manager --add-repo "https://download.docker.com/linux/${repo_id}/docker-ce.repo"
    else
        echo "No compatible package manager found. Please install Docker manually."
        exit 1
    fi
    do_install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || \
    do_install docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo systemctl enable --now docker
}
if ! command -v docker >/dev/null 2>&1; then
    case "$OS_ID" in
        ubuntu|debian) install_docker_deb_family ;;
        fedora|centos|rocky|rhel) install_docker_rpm_family ;;
        *)
            echo "Unsupported OS for Docker installation: $OS_ID"
            exit 1
            ;;
    esac
fi
#################################################
# Post Install
# https://docs.docker.com/engine/install/linux-postinstall/
#################################################
CURRENT_USER="$(whoami)"
echo "Creating docker group if needed..."
sudo groupadd docker > /dev/null 2>&1 || true
echo "Adding ${CURRENT_USER} to docker group..."
sudo usermod -aG docker "${CURRENT_USER}" > /dev/null 2>&1 || true
#
if ! docker version > /dev/null 2>&1; then
    if [ -z "$REENTERED_WITH_DOCKER" ]; then
        echo "Docker group change needs session reload. Re-executing to apply..."
        exec sudo -iu "$CURRENT_USER" env REENTERED_WITH_DOCKER=1 sh "$_SCRIPT_PATH"
    else
        echo "Docker still not available. Try logging out and in again, or rebooting."
        exit 1
    fi
fi
#
# Set Docker daemon log limits
DAEMON_CONFIG_FILE="/etc/docker/daemon.json"
TMP_DAEMON_CONFIG="_etc_docker_daemon.json"
cat > "$TMP_DAEMON_CONFIG" <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "3m",
    "max-file": "1"
  }
}
EOF
#
if [ ! -f "$DAEMON_CONFIG_FILE" ] || ! cmp -s "$TMP_DAEMON_CONFIG" "$DAEMON_CONFIG_FILE"; then
    echo "Applying Docker daemon log configuration..."
    sudo mkdir /etc/docker
    sudo cp "$TMP_DAEMON_CONFIG" "$DAEMON_CONFIG_FILE"
    sudo systemctl restart docker
else
    echo "Docker daemon configuration already set."
fi
#
rm -f "$TMP_DAEMON_CONFIG"
##################################################################################################
#
##################################################################################################
# Nginx
##################################################################################################
do_install nginx
if [ "$(systemctl is-active nginx)" = "inactive" ]; then
    echo "Nginx is not running. Starting it..."
    sudo systemctl start nginx
fi
if [ -f "/etc/nginx/sites-available/default" ]; then
    NGINX_CONF="/etc/nginx/sites-available/default"
elif [ -f "/etc/nginx/nginx.conf" ]; then
    echo "Default site config not found, falling back to nginx.conf"
    NGINX_CONF="/etc/nginx/nginx.conf"
else
    echo "Nginx configuration file not found. Exiting."
    exit 1
fi
#
if grep -qE '^\s*server_name\s+_;' "${NGINX_CONF}"; then
    echo "Updating server_name in default Nginx config..."
    sudo sed -i "s/^\s*server_name\s\+_;/    server_name ${DOMAIN_NAME};/" "${NGINX_CONF}"
    sudo systemctl reload nginx
else
    echo "Nginx config already uses a custom server_name — skipping update."
fi
#
# Check if Nginx is running
if [ "$(systemctl is-active nginx)" = "inactive" ]; then
    echo "Nginx is not running. Starting it..."
    sudo systemctl start nginx
    sleep 5
fi
#
# Check if Nginx is running once more
if [ "$(systemctl is-active nginx)" = "inactive" ]; then
    echo "Nginx is still not running. Please check the logs."
    sudo journalctl -u nginx
    exit 1
fi
##################################################################################################
# Certbot
##################################################################################################
try_install_certbot() {
    #
    if ! command -v certbot >/dev/null 2>&1; then
        echo "Trying to install certbot via snap..."
        if ! command -v snap >/dev/null 2>&1; then
            do_install snapd
            # https://snapcraft.io/install/certbot/rhel
            # https://snapcraft.io/install/certbot/debian
            # https://snapcraft.io/install/certbot/fedora
            # https://snapcraft.io/install/certbot/centos
            # https://snapcraft.io/docs/installing-snap-on-rocky
            if [ "$OS_ID" = "rhel" ] || [ "$OS_ID" = "rocky" ] || [ "$OS_ID" = "centos" ] || [ "$OS_ID" = "fedora" ]; then
                sudo systemctl enable --now snapd.socket
            else
                sudo systemctl enable --now snapd
            fi
        fi
        if ! command -v snap >/dev/null 2>&1; then
            echo "Could not find or install snap. Please install it manually and try again."
            exit 1
        fi
        until snap list >/dev/null 2>&1; do
            echo "Waiting for snapd to finish initializing..."
            sleep 3
        done
        sudo ln -s /var/lib/snapd/snap /snap > /dev/null 2>&1 || true
        sudo ln -s /snap/bin/certbot /usr/bin/certbot  > /dev/null 2>&1 || true
        sudo snap install --classic certbot
    fi
    # check again
    if ! command -v certbot >/dev/null 2>&1; then
        echo "Certbot is not installed. Please check your installation."
        exit 1
    fi
}
if [ "$SKIP_CERTBOT" = "1" ]; then
    echo "Skipping domain reachability check and certbot execution (--skip-certbot enabled)"
    echo "Certbot will be installed, but no certificate will be issued."
    try_install_certbot
else
    # before, check if we are available to the outside world
    echo "Checking if ${DOMAIN_NAME} is reachable over HTTP..."
    if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://${DOMAIN_NAME}/" | grep -qE '^(2|3)[0-9]{2}$'; then
        echo "${DOMAIN_NAME} is reachable"
    else
        echo "${DOMAIN_NAME} seems to be unreachable. Please check your DNS settings and/or any firewall rules."
        exit 1
    fi
    try_install_certbot
    if [ -n "${CERTBOT_EMAIL}" ]; then
        echo "Running certbot with provided email: ${CERTBOT_EMAIL} ..."
        sudo certbot --nginx -d "${DOMAIN_NAME}" \
            --agree-tos \
            --redirect \
            --hsts \
            --staple-ocsp \
            --reuse-key \
            --non-interactive \
            --quiet \
            --deploy-hook "true" \
            --no-eff-email \
            -m "${CERTBOT_EMAIL}"
    else
        echo "Running certbot without email (unsafe)..."
        sudo certbot --nginx -d "${DOMAIN_NAME}" \
            --agree-tos \
            --redirect \
            --hsts \
            --staple-ocsp \
            --reuse-key \
            --non-interactive \
            --quiet \
            --deploy-hook "true" \
            --no-eff-email \
            --register-unsafely-without-email
    fi
    #
    sudo nginx -t
    sudo systemctl reload nginx
fi
#
##################################################################################################
# Setup the runner
##################################################################################################
#
if [ -d "runner_tmp" ]; then
    rm -rf runner_tmp
fi
git clone https://github.com/waldiez/runner.git runner_tmp
cd runner_tmp
cp compose.example.yaml ../compose.yaml
python scripts/image.py --container-command docker
cd ..
rm -rf runner_tmp
#
# set env vars
#
echo "WALDIEZ_RUNNER_DOMAIN_NAME=${DOMAIN_NAME}" > .env
chmod 600 .env
#
client_id="$(python -c 'import secrets; secrets;print(secrets.token_hex(32))')"
client_secret="$(python -c 'import secrets; secrets;print(secrets.token_hex(64))')"
redis_password="$(python -c 'import secrets; secrets;print(secrets.token_hex(8))')"
db_password="$(python -c 'import secrets; secrets;print(secrets.token_hex(8))')"
secret_key="$(python -c 'import secrets; secrets;print(secrets.token_hex(64))')"
#
# to .env
echo "REDIS_PASSWORD=wz-${redis_password}" >> .env
echo "POSTGRES_PASSWORD=wz-${db_password}" >> .env
#
echo "WALDIEZ_RUNNER_REDIS_PASSWORD=wz-${redis_password}" >> .env
echo "WALDIEZ_RUNNER_LOCAL_CLIENT_ID=wz-${client_id}" >> .env
echo "WALDIEZ_RUNNER_LOCAL_CLIENT_SECRET=wz-${client_secret}" >> .env
echo "WALDIEZ_RUNNER_DB_PASSWORD=wz-${db_password}" >> .env
echo "WALDIEZ_RUNNER_SECRET_KEY=wz-${secret_key}" >> .env
echo "WALDIEZ_RUNNER_FORCE_SSL=1" >> .env
#
. ./.env
#
# make sure the external network is created
docker network create waldiez-external > /dev/null 2>&1 || true
#
# a final check
docker compose -f compose.yaml config
#
echo "Compose is ready. Please double-check the compose.yaml file and the .env file."
echo "When ready (e.g. after a reboot for group changes or dist-upgrades), run the following to start the containers:"
echo
echo "cd $(pwd)"
echo "docker compose -f compose.yaml up -d"
echo
#
echo "To check the status of the containers:"
echo "docker compose -f compose.yaml ps"
echo
#
echo "To view logs for a container:"
echo "docker compose -f compose.yaml logs <container_name>"
echo "Or, with plain Docker:"
echo "docker logs <container_name>"
echo
#
echo "To stop the containers:"
echo "docker compose -f compose.yaml down"
echo
#
echo "To stop and remove containers and volumes:"
echo "docker compose -f compose.yaml down --volumes"
echo
#
echo "To stop and remove containers, volumes, and images:"
echo "docker compose -f compose.yaml down --rmi all --volumes"
echo
