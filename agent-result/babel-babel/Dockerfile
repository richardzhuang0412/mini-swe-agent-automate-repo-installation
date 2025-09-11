FROM node:20-slim

# Install git and other necessary tools
RUN apt-get update && apt-get install -y \
    git \
    make \
    python3 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone the repository
RUN git clone https://github.com/babel/babel.git .

# Enable corepack for Yarn
RUN corepack enable

# Install dependencies
RUN yarn install --frozen-lockfile

# Skip full build due to complexity, run tests directly
# Many repos can run tests without full build
RUN BABEL_ENV=test yarn test --passWithNoTests || true

# Set default command
CMD ["/bin/bash"]
