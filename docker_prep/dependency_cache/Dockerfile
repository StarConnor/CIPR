FROM node:20-bookworm

ARG DEBIAN_FRONTEND=noninteractive
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    no_proxy=localhost,127.0.0.1,::1,${NO_PROXY} \
    NO_PROXY=localhost,127.0.0.1,::1,${NO_PROXY}

RUN apt-get update && apt-get install -y --no-install-recommends \
    apt-cacher-ng \
    ca-certificates \
    curl \
    gnupg \
    nginx \
    python3 \
    python3-pip \
    supervisor \
    tini \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g verdaccio@6
RUN python3 -m pip install --index-url https://mirrors.ustc.edu.cn/pypi/simple --no-cache-dir --break-system-packages devpi-server==6.* devpi-client==7.*

COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/dependency-cache.conf
COPY verdaccio.yaml /etc/verdaccio/config.yaml
COPY start-devpi.sh /usr/local/bin/start-devpi.sh
COPY entrypoint.sh /usr/local/bin/dependency-cache-entrypoint.sh
RUN chmod +x /usr/local/bin/start-devpi.sh /usr/local/bin/dependency-cache-entrypoint.sh \
    && mkdir -p /cache/apt-cacher-ng /cache/verdaccio /cache/devpi /cache/nginx \
    && mkdir -p /var/log/supervisor /run/nginx \
    && chown -R root:root /cache

VOLUME ["/cache"]

EXPOSE 3141 3142 4873 3010 18082 18083 18084 9292

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/dependency-cache-entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/dependency-cache.conf"]
