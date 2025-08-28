FROM node:18-slim

WORKDIR /app

# Install git and required build dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone the repository
RUN git clone https://github.com/expressjs/express.git .

# Install dependencies
RUN npm install

# Run tests to verify the setup
RUN npm test

# Set the default command
CMD ["npm", "start"]
