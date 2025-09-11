FROM node:18-slim

# Install git for cloning the repository
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone the Express.js repository
RUN git clone https://github.com/expressjs/express.git .

# Install dependencies
RUN npm install

# Set environment variables for testing
ENV NODE_ENV=test
ENV NO_DEPRECATION=body-parser,express

# Run tests to verify the build
RUN npm test

# Reset environment for runtime
ENV NODE_ENV=production

# Expose common Express port
EXPOSE 3000

# Default command to start an interactive bash shell
CMD ["/bin/bash"]
