init: docker-down docker-pull docker-network docker-build docker-up

up: docker-up
down: docker-down
restart: down up

clear: docker-clear
clear-force: docker-clear-force

docker-up:
	docker compose up -d

docker-down:
	docker compose down --remove-orphans

docker-pull:
	docker compose pull

docker-build:
	docker compose build --pull

docker-network:
	docker network create traefik-public || true

docker-clear:
	docker compose exec dockerhub bin/registry garbage-collect /dockerhub/garbage.yml [--delete-untagged] \
	&& docker system prune -af --all

docker-clear-force:
	rm -rf /var/lib/docker/volumes/traefik_dockerhub/_data/docker/registry/v2 \
	&& docker system prune -af --all
