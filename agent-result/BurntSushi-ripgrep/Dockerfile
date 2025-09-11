FROM rust:1.88-slim

# Install git and other necessary tools
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone the repository
RUN git clone https://github.com/BurntSushi/ripgrep.git .

# Build the project
RUN cargo build --release

# Run tests with verbose output
RUN cargo test --all -- --nocapture

# Set the default command
CMD ["/bin/bash"]
