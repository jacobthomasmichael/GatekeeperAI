FROM alpine:3.19

RUN apk add --no-cache openssh git curl bash \
    && adduser -D -s /bin/bash git \
    && mkdir -p /home/git/.ssh /git-repos \
    && chmod 700 /home/git/.ssh \
    && chown -R git:git /home/git /git-repos \
    && ssh-keygen -A

COPY sshd_config /etc/ssh/sshd_config
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
