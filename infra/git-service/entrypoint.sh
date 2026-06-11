#!/bin/bash
set -e

# Ensure git-repos directory is owned by the git user
chown -R git:git /git-repos

# Set up authorized_keys
touch /home/git/.ssh/authorized_keys
chown git:git /home/git/.ssh/authorized_keys
chmod 600 /home/git/.ssh/authorized_keys

# Write GATEKEEPER_API_URL into the git user's environment so post-receive hooks
# can call the correct internal API address (http://api:8000 in Docker).
echo "GATEKEEPER_API_URL=${GATEKEEPER_API_URL:-http://localhost:8000}" \
    > /home/git/.ssh/environment
chmod 600 /home/git/.ssh/environment
chown git:git /home/git/.ssh/environment

exec /usr/sbin/sshd -D -e
