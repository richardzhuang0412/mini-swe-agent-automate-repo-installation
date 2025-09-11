FROM node:18-slim

# Install system dependencies needed for canvas and other native modules
RUN apt-get update && apt-get install -y \
    git \
    python3 \
    make \
    g++ \
    libcairo2-dev \
    libpango1.0-dev \
    libjpeg-dev \
    libgif-dev \
    librsvg2-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone the repository
RUN git clone https://github.com/diegomura/react-pdf.git .

# Install dependencies
RUN yarn install --frozen-lockfile

# Build the project
RUN yarn build

# Run tests in verbose mode
RUN yarn test --reporter=verbose

# Set default command
CMD ["/bin/bash"]
