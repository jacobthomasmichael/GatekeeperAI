#!/bin/bash
set -e

# Ensure git-repos directory is owned by the git user
chown -R git:git /git-repos

# Set up authorized_keys — in Kubernetes the file is mounted read-only from a
# ConfigMap, so these operations may be no-ops; ignore errors gracefully.
touch /home/git/.ssh/authorized_keys 2>/dev/null || true
chown git:git /home/git/.ssh/authorized_keys 2>/dev/null || true
chmod 600 /home/git/.ssh/authorized_keys 2>/dev/null || true

# Write GATEKEEPER_API_URL into the git user's environment so post-receive hooks
# can call the correct internal API address (http://api:8000 in Docker).
echo "GATEKEEPER_API_URL=${GATEKEEPER_API_URL:-http://localhost:8000}" \
    > /home/git/.ssh/environment
chmod 600 /home/git/.ssh/environment
chown git:git /home/git/.ssh/environment

exec /usr/sbin/sshd -D -e
