FROM rust:1-slim

# Minimal tools for building Rust crates and cloning the repo
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    build-essential \
    pkg-config \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone the repository
RUN git clone https://github.com/servo/html5ever.git .

# Fetch dependencies and run tests to verify everything works
# (This will fail the image build if tests fail)
RUN cargo test

# Default to an interactive shell for development/CI usage
CMD ["/bin/bash"]
