FROM rust:1.83-slim

# Install git for cloning and submodule operations
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone the repository
RUN git clone https://github.com/servo/html5ever.git .

# Initialize submodules for test suite
RUN git submodule update --init

# Build the project
RUN cargo build --all

# Run tests with verbose output
RUN cargo test --all -- --nocapture

# Run tendril tests with encoding features
RUN cargo test -p tendril --features 'encoding encoding_rs' -- --nocapture

CMD ["/bin/bash"]
