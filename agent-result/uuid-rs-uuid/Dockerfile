FROM rust:1.70-slim

# Install git and other necessary tools
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone the repository
RUN git clone https://github.com/uuid-rs/uuid.git .

# Build the project and run tests to verify everything works
RUN cargo test --all-features

# Also run doc tests and example tests as per CI
RUN cargo test --all-features --doc
RUN cargo test --all-features --examples

# Set environment variables for uuid_unstable features (as used in CI)
ENV RUSTFLAGS="--cfg uuid_unstable"
ENV RUSTDOCFLAGS="--cfg uuid_unstable"

# Run additional tests with unstable features
RUN cargo test --all-features

# Default command to run bash for interactive use
CMD ["/bin/bash"]
