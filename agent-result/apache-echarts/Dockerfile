FROM node:18-slim

LABEL org.opencontainers.image.source="https://github.com/apache/echarts"
ENV CI=true

# Install minimal system dependencies for cloning and potential native builds
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates python3 build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Clone the repository
RUN git clone https://github.com/apache/echarts.git . \
 && git submodule update --init --recursive || true

# Enable Corepack for pnpm/yarn support, install dependencies, and run tests/build
RUN corepack enable \
 && if [ -f pnpm-lock.yaml ] || ( [ -f package.json ] && grep -q '"packageManager"[[:space:]]*:[[:space:]]*"pnpm@' package.json ); then \
      corepack prepare pnpm@latest --activate; \
      pnpm install --frozen-lockfile || pnpm install; \
      (pnpm -s test || pnpm -s run test || pnpm -s run ci || pnpm -s run build); \
    elif [ -f yarn.lock ] || ( [ -f package.json ] && grep -q '"packageManager"[[:space:]]*:[[:space:]]*"yarn@' package.json ); then \
      corepack prepare yarn@stable --activate; \
      yarn install --frozen-lockfile || yarn install; \
      (yarn -s test || yarn -s run test || yarn -s run ci || yarn -s build); \
    else \
      npm ci || npm install; \
      (npm -s test --if-present || npm -s run ci --if-present || npm -s run build --if-present || true); \
    fi

# Default to an interactive shell for development/CI usage
CMD ["/bin/bash"]
