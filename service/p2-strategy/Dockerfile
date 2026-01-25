# Dockerfile for P2 Strategy Services
# Usage:
#   docker build --build-arg SERVICE=frontend -t p2-strategy-frontend .
#   docker build --build-arg SERVICE=config-poller -t p2-strategy-config-poller .
#   docker build --build-arg SERVICE=execution-poller -t p2-strategy-execution-poller .

FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install
COPY code/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY code/ .

# Copy and setup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose Flask port (only used by frontend)
EXPOSE 8082

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Build argument to specify which service to run
ARG SERVICE=frontend

# Set the service as an environment variable for runtime
ENV SERVICE=${SERVICE}

# Use entrypoint script for proper signal handling
ENTRYPOINT ["/entrypoint.sh"]
