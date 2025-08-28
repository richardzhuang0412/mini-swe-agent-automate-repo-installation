FROM node:18-slim

WORKDIR /app

# Install git and build essentials for native dependencies
RUN apt-get update && \
    apt-get install -y git build-essential python3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Clone the repository
RUN git clone https://github.com/apache/echarts.git .

# Install dependencies
RUN npm install

# Build the project
RUN npm run build:lib && \
    npm run build:i18n && \
    npm run build && \
    npm run build:esm && \
    npm run build:extension && \
    npm run build:ssr

# Run tests
RUN npm test

# Set default command
CMD ["node"]

