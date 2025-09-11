FROM node:18-slim

# Install minimal tools needed to clone the repo
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Clone the repository into the image
RUN git clone https://github.com/expressjs/express.git .

# Show tool versions for diagnostics
RUN node -v && npm -v

# Install dependencies (prefer lockfile if present)
RUN npm ci || npm install --no-audit --no-fund

# Run tests to verify the build
RUN npm test

# Default to an interactive shell for development/CI usage
CMD ["/bin/bash"]
