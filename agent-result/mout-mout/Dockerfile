FROM node:18-slim

# Install git for cloning the repository
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone the repository
RUN git clone https://github.com/mout/mout.git .

# Install dependencies
RUN npm install

# Run tests to verify the build (this also runs the pretest build step)
RUN npm test -- --reporter spec

# Default command
CMD ["/bin/bash"]
