#!/usr/bin/env sh
# shellcheck disable=SC2129,SC1091

# example usage:

# DOMAIN_NAME=example.com sh -c "$(curl -fsSL https://raw.githubusercontent.com/waldiez/runner/refs/heads/main/deploy/compose/ubuntu.sh)"

set -e

# Absolute path to self
_SCRIPT_PATH="$(readlink -f "$0")"
_MY_DIR="$(dirname "$_SCRIPT_PATH")"
_ENV_FILE_NAME="waldiez_runner_env.sh"
_ENV_FILE="$(dirname "$_SCRIPT_PATH")/${_ENV_FILE_NAME}"

cd "${_MY_DIR}" || exit 1

if [ -f "${_ENV_FILE}" ]; then
    # shellcheck disable=SC1090
    . "${_ENV_FILE}"
fi

# env vars used
DOMAIN_NAME="${DOMAIN_NAME:-}"  # required
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"  # optional

# optional arguments that can be passed to the script
while [ $# -gt 0 ]; do
    case "$1" in
        --domain-name)
            DOMAIN_NAME="$2"
            shift 2
            ;;
        --certbot-email)
            CERTBOT_EMAIL="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

if [ -z "${DOMAIN_NAME}" ]; then
    echo "DOMAIN_NAME is required. Set it via ${_ENV_FILE_NAME}.sh, environment, or --domain-name"
    exit 1
fi
# set the current values after env check and args check
cat > "$_ENV_FILE" <<EOF
DOMAIN_NAME="${DOMAIN_NAME}"
CERTBOT_EMAIL="${CERTBOT_EMAIL}"
EOF

# shellcheck disable=SC1090
. "${_ENV_FILE}"


##################################################################################################
# User running the script
##################################################################################################
# Find first sudo-capable user
find_sudo_user() {
    getent group sudo | cut -d: -f4 | tr ',' '\n' | grep -Ev '^\s*$' | head -n 1
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

# Find unused UID, avoiding matching GID
find_user_id() {
    new_group_id="$1"
    if [ -z "${new_group_id}" ]; then
        echo "No group ID provided"
        exit 1
    fi
    try_uid=1000
    while [ "$try_uid" -lt 60000 ]; do
        if [ "$try_uid" -ne "${new_group_id}" ] && ! getent passwd "${try_uid}" > /dev/null 2>&1; then
            echo "${try_uid}"
            return
        fi
        try_uid=$((try_uid + 1))
    done
    echo "No available UID found"
    exit 1
}

if [ "$(id -u)" -eq 0 ]; then
    SUDO_USER="$(find_sudo_user)"

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
        addgroup --gid "${group_id}" "${user_name_and_group}"

        echo "Creating user '${user_name_and_group}' (UID ${user_id})..."
        adduser --disabled-password --gecos '' --shell /bin/bash \
                --uid "${user_id}" --gid "${group_id}" "${user_name_and_group}"

        echo "Adding user to sudo group..."
        usermod -aG sudo "${user_name_and_group}"

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
    cp "${_SCRIPT_PATH}" "${SCRIPT_COPY}"
    chown "${SUDO_USER}:${SUDO_USER}" "${SCRIPT_COPY}"
    chmod +rx "${SCRIPT_COPY}"

    # let's also pass the env file
    cp "${_ENV_FILE}" "${USER_HOME}/${_ENV_FILE_NAME}" 2>/dev/null || true
    chown "${SUDO_USER}:${SUDO_USER}" "${USER_HOME}/${_ENV_FILE_NAME}" 2>/dev/null || true

    exec sudo -u "${SUDO_USER}" sh "${SCRIPT_COPY}"
fi

echo "Running as user: $(whoami)"

sudo apt update && sudo apt dist-upgrade -y
sudo apt install -y make python-is-python3


##################################################################################################
# Docker
##################################################################################################
# # https://docs.docker.com/engine/install/ubuntu/
# # https://docs.docker.com/engine/install/linux-postinstall/
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-${VERSION_CODENAME}}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

CURRENT_USER="$(whoami)"

echo "Creating docker group if needed..."
sudo groupadd docker > /dev/null 2>&1 || true
echo "Adding ${CURRENT_USER} to docker group if needed..."
sudo usermod -aG docker "${CURRENT_USER}" > /dev/null 2>&1 || true

# Check if Docker works without sudo
if ! docker version > /dev/null 2>&1; then
    if [ -z "${REENTERED_WITH_DOCKER}" ]; then
        echo "Docker not accessible yet. Re-executing script with updated group..."

        exec su - "${CURRENT_USER}" -c "REENTERED_WITH_DOCKER=1 sh '${_SCRIPT_PATH}'"
    else
        echo "Still can't access Docker even after group change. You may need to log out and in again."
        exit 1
    fi
fi

echo "Configuring Docker log limits..."

DAEMON_CONFIG_FILE="/etc/docker/daemon.json"
TMP_DAEMON_CONFIG="____docker_daemon.json.tmp"
# desired config:
cat > "$TMP_DAEMON_CONFIG" <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "3m",
    "max-file": "1"
  }
}
EOF

# Only update if needed
if [ ! -f "${DAEMON_CONFIG_FILE}" ] || ! cmp -s "${TMP_DAEMON_CONFIG}" "${DAEMON_CONFIG_FILE}"; then
    echo "Applying Docker daemon config..."
    sudo cp "${TMP_DAEMON_CONFIG}" "${DAEMON_CONFIG_FILE}"
    sudo systemctl restart docker
    echo "Docker log config applied and daemon restarted."
else
    echo "Docker daemon config already up to date."
fi

rm -f "${TMP_DAEMON_CONFIG}"

##################################################################################################
# Nginx
##################################################################################################
sudo apt install -y nginx
NGINX_CONF="/etc/nginx/sites-available/default"

if grep -qE '^\s*server_name\s+_;' "${NGINX_CONF}"; then
    echo "Updating server_name in default Nginx config..."
    sudo sed -i "s/^\s*server_name\s\+_;/    server_name ${DOMAIN_NAME};/" "${NGINX_CONF}"
    sudo systemctl reload nginx
else
    echo "Nginx config already uses a custom server_name — skipping update."
fi

# Check if Nginx is running
if [ "$(systemctl is-active nginx)" = "inactive" ]; then
    echo "Nginx is not running. Starting it..."
    sudo systemctl start nginx
    sleep 5
fi

# Check if Nginx is running once more
if [ "$(systemctl is-active nginx)" = "inactive" ]; then
    echo "Nginx is still not running. Please check the logs."
    sudo journalctl -u nginx
    exit 1
fi

##################################################################################################
# Certbot
##################################################################################################

# before, check if we are available to the outside world

echo "Checking if ${DOMAIN_NAME} is reachable over HTTP..."

if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://${DOMAIN_NAME}/" | grep -qE '^(2|3)[0-9]{2}$'; then
    echo "${DOMAIN_NAME} is reachable"
else
    echo "${DOMAIN_NAME} seems to be unreachable. Please check your DNS settings and/or any firewall rules."
    exit 1
fi

# https://certbot.eff.org/instructions?ws=nginx&os=snap
sudo snap install --classic certbot
# might already be installed, so let's ignore the error
sudo ln -s /snap/bin/certbot /usr/bin/certbot  > /dev/null 2>&1 || true

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

sudo systemctl reload nginx


##################################################################################################
# Setup the runner
##################################################################################################

if [ -d "runner_tmp" ]; then
    rm -rf runner_tmp
fi
git clone https://github.com/waldiez/runner.git runner_tmp
cd runner_tmp
cp compose.example.yaml ../compose.yaml
make image
cd ..
rm -rf runner_tmp

# set env vars

echo "WALDIEZ_RUNNER_DOMAIN_NAME=${DOMAIN_NAME}" > .env

client_id="$(python -c 'import secrets; secrets;print(secrets.token_hex(32))')"
client_secret="$(python -c 'import secrets; secrets;print(secrets.token_hex(64))')"
redis_password="$(python -c 'import secrets; secrets;print(secrets.token_hex(8))')"
db_password="$(python -c 'import secrets; secrets;print(secrets.token_hex(8))')"
secret_key="$(python -c 'import secrets; secrets;print(secrets.token_hex(64))')"

# to .env
echo "REDIS_PASSWORD=wz-${redis_password}" >> .env
echo "POSTGRES_PASSWORD=wz-${db_password}" >> .env

echo "WALDIEZ_RUNNER_REDIS_PASSWORD=wz-${redis_password}" >> .env
echo "WALDIEZ_RUNNER_LOCAL_CLIENT_ID=wz-${client_id}" >> .env
echo "WALDIEZ_RUNNER_LOCAL_CLIENT_SECRET=wz-${client_secret}" >> .env
echo "WALDIEZ_RUNNER_DB_PASSWORD=wz-${db_password}" >> .env
echo "WALDIEZ_RUNNER_SECRET_KEY=wz${secret_key}" >> .env
echo "WALDIEZ_RUNNER_FORCE_SSL=1" >> .env

. ./.env

# make sure the external network is created
docker network create waldiez-external > /dev/null 2>&1 || true

# a final check
docker compose -f compose.yaml config

echo "Compose is ready. do double check the compose.yaml file and the .env file."
echo "If ready (if needed [e.g. in vanilla setup] you might want to do a reboot) run the following commands to start the containers:"
echo "cd $(pwd)"
echo "docker compose -f compose.yaml up -d"
