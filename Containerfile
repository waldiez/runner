#####################################################################################
FROM python:3.12-slim

LABEL maintainer="waldiez <development@waldiez.io>"
LABEL org.opencontainers.image.source="quay.io/waldiez/runner"
LABEL org.opencontainers.image.title="waldiez/runner"
LABEL org.opencontainers.image.description="Waldiez runner allows you to run Waldiez flows in isolated environments"

# set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND="noninteractive"
ENV DEBCONF_NONINTERACTIVE_SEEN=true

# install system dependencies
# that might be later needed when running the
# flows (e.g. additional dependencies based on the tools and agents used)
RUN apt update && \
    apt upgrade -y && \
    apt install -y --no-install-recommends \
    build-essential \
    bzip2 \
    curl \
    ca-certificates \
    zip \
    unzip \
    git \
    jq \
    ffmpeg \
    graphviz \
    libpq-dev\
    wget \
    fonts-liberation \
    openssl \
    libcairo2-dev \
    libpango1.0-dev \
    libjpeg-dev \
    libgif-dev \
    librsvg2-dev \
    libpq-dev\
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    tzdata \
    locales \
    pandoc \
    xdg-utils \
    xvfb \
    firefox-esr \
    chromium && \
    sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen en_US.UTF-8 && \
    curl -fsSL https://deb.nodesource.com/setup_22.x -o nodesource_setup.sh && \
    bash nodesource_setup.sh && \
    rm nodesource_setup.sh && \
    apt install -y nodejs && \
    npm install -g corepack && \
    corepack enable && \
    yarn set version stable && \
    npx playwright install-deps && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /var/cache/apt/archives/*

# Add ChromeDriver
RUN CHROME_VERSION=$(chromium --version | grep -oP '\d+\.\d+\.\d+') && \
    echo "Chrome version: $CHROME_VERSION" && \
    DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" | \
    jq -r --arg ver "$CHROME_VERSION" '.channels.Stable.version') && \
    echo "Driver version: $DRIVER_VERSION" && \
    curl -Lo /tmp/chromedriver.zip "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin && \
    mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /usr/local/bin/chromedriver-linux64

# Add GeckoDriver (for Firefox)
RUN GECKO_VERSION=$(curl -s https://api.github.com/repos/mozilla/geckodriver/releases/latest | jq -r '.tag_name') && \
    curl -Lo /tmp/geckodriver.tar.gz "https://github.com/mozilla/geckodriver/releases/download/${GECKO_VERSION}/geckodriver-${GECKO_VERSION}-linux64.tar.gz" && \
    tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin && \
    chmod +x /usr/local/bin/geckodriver && \
    rm /tmp/geckodriver.tar.gz

# Ensure /usr/local/bin is in the PATH
ENV PATH="/usr/local/bin:${PATH}"

# Set locale and timezone
ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    LC_CTYPE=en_US.UTF-8 \
    TZ=Etc/UTC

# let's hope this will not be needed (e.g. no need to open a shell)
# if it does, I like colors
RUN sed -i 's/^#force_color_prompt=yes/force_color_prompt=yes/' /etc/skel/.bashrc

# add a non-root user and group
ARG GROUP_ID=1000
ENV GROUP_ID=${GROUP_ID}
RUN addgroup --system --gid ${GROUP_ID} waldiez
ARG USER_ID=1000
ENV USER_ID=${USER_ID}
RUN adduser --disabled-password --gecos '' --shell /bin/bash --uid ${USER_ID} --gid ${GROUP_ID} waldiez
RUN mkdir -p /home/waldiez/.local/bin /home/waldiez/app /home/waldiez/app/waldiez_runner/storage && \
    chown -R waldiez:waldiez /home/waldiez
ENV PATH=/home/waldiez/.local/bin:${PATH}

USER waldiez

RUN npx playwright install chromium firefox
RUN pip install --upgrade pip

COPY --chown=waldiez:waldiez requirements/main.txt /home/waldiez/requirements.txt
RUN pip install -r /home/waldiez/requirements.txt && rm /home/waldiez/requirements.txt

COPY --chown=waldiez:waldiez . /home/waldiez/app
RUN chmod +x /home/waldiez/app/scripts/start.sh

EXPOSE 8888
VOLUME /home/waldiez/app/waldiez_runner/storage

WORKDIR /home/waldiez/app


ENV TINI_SUBREAPER=true
ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["/home/waldiez/app/scripts/start.sh"]
