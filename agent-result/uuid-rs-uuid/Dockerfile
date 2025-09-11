FROM rust:1.70-slim

# Install git for cloning the repository
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone the repository
RUN git clone https://github.com/uuid-rs/uuid.git .

# Run tests with all features and verbose output
RUN cargo test --all-features --verbose

# Set up the environment for development use
CMD ["/bin/bash"]
