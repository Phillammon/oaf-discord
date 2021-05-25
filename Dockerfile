FROM python:3.9.5-slim

# Set pip to have no saved cache
ENV PIP_NO_CACHE_DIR=false

# Define Git SHA build argument
ARG git_sha="development"

# Set Git SHA environment variable for Sentry
ENV GIT_SHA=$git_sha

# Copy the source code in last to optimize rebuilding the image
COPY . .

ENTRYPOINT ["python3"]
CMD ["./oaf/oaf.py"]