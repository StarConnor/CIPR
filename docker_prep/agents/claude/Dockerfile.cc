FROM base-env

COPY claude-code.tgz /
USER root
WORKDIR /home/devuser
RUN npm install -g /claude-code.tgz

USER devuser
COPY --chown=devuser:devuser .claude /home/devuser/.claude
COPY --chown=devuser:devuser .claude.json /home/devuser/.claude.json
COPY --chown=devuser:devuser .claude.json.backup /home/devuser/.claude.json.backup

ENV PYTHONPATH=/app:$PYTHONPATH

USER root
RUN rm /claude-code.tgz

USER devuser
WORKDIR /home/devuser/project

# Agent configuration via environment variables
ENV AGENT_TYPE=claude-code
ENV ENABLE_MITM=true
ENV ENABLE_STRACE=true
ENV LOG_LEVEL=INFO

USER root

# docker build -t cli-env:cc -f Dockerfile.cc .
