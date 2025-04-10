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
    tzdata \
    locales \
    bzip2 \
    ca-certificates \
    build-essential \
    libcairo2-dev \
    libpango1.0-dev \
    libjpeg-dev \
    libgif-dev \
    librsvg2-dev \
    libpq-dev\
    wget \
    fonts-liberation \
    git \
    openssl \
    pandoc \
    sudo \
    curl \
    tini \
    zip \
    unzip \
    graphviz && \
    sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen en_US.UTF-8 && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /var/cache/apt/archives/*

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    LC_CTYPE=en_US.UTF-8 \
    TZ=Etc/UTC

# install nodejs
RUN curl -fsSL https://deb.nodesource.com/setup_22.x -o nodesource_setup.sh && \
    bash nodesource_setup.sh && \
    apt install -y nodejs && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /var/cache/apt/archives/*

# install yarn
RUN npm install -g corepack && \
    corepack enable && \
    yarn set version stable

# let's hope this will not be needed (e.g. no need to open a shell)
# if it does, I like colors
RUN sed -i 's/^#force_color_prompt=yes/force_color_prompt=yes/' /etc/skel/.bashrc

# add a non-root user
ARG GROUP_ID=1000
ENV GROUP_ID=${GROUP_ID}
RUN addgroup --system --gid ${GROUP_ID} user
ARG USER_ID=1000
ENV USER_ID=${USER_ID}
RUN adduser --disabled-password --gecos '' --shell /bin/bash --uid ${USER_ID} --gid ${GROUP_ID} user
RUN mkdir -p /home/user/.local/bin /home/user/waldiez_runner /home/user/waldiez_runner/storage && \
    chown -R user:user /home/user
ENV PATH=/home/user/.local/bin:${PATH}

USER user
RUN pip install --upgrade pip

COPY --chown=user:user requirements/main.txt /home/user/requirements.txt
RUN pip install -r /home/user/requirements.txt && rm /home/user/requirements.txt

# make sure we can also install pysqlite3[-binary]
# on arm, pysqlite3[-binary] is not available
# on PyPI, so we need to manually install it from source
RUN mkdir -p /home/user/_tmp && \
    cd /home/user/_tmp && \
    python -c \
    'from waldiez.utils.pysqlite3_checker import install_pysqlite3, download_sqlite_amalgamation; p=download_sqlite_amalgamation(); install_pysqlite3(p);' && \
    python -c \
    'from waldiez.utils.pysqlite3_checker import check_pysqlite3; check_pysqlite3()' && \
    rm -rf /home/user/_tmp


COPY --chown=user:user . /home/user
RUN chmod +x /home/user/scripts/start.sh

EXPOSE 8888
VOLUME /home/user/waldiez_runner/storage

WORKDIR /home/user


ENV TINI_SUBREAPER=true
ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["/home/user/scripts/start.sh"]
