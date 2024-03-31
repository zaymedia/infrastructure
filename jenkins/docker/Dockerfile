FROM jenkins/jenkins:alpine

USER root

RUN apk update \
    && apk add --no-cache make gettext docker-cli-compose

USER jenkins
