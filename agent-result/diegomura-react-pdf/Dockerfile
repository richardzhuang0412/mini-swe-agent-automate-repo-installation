FROM node:18

# Set working directory
WORKDIR /app

# Clone the repository
RUN git clone https://github.com/diegomura/react-pdf.git .

# Install dependencies using yarn with frozen lockfile
RUN yarn --frozen-lockfile

# Build the project
RUN yarn build

# Run tests to verify the build
RUN yarn test

# Set the default command
CMD ["/bin/bash"]
