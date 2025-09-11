FROM node:18-slim

# Install git to clone the repository
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone the repository
RUN git clone https://github.com/apache/echarts.git .

# Install dependencies
RUN npm ci

# Run tests with verbose output
RUN npm run test -- --verbose

# Set default command
CMD ["/bin/bash"]
