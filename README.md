### Предварительные настройки
1. Обновление пакетов
```
sudo apt update
```

2. Установка утилиты make:
```
sudo apt install make
```

3. Установка Docker:
```
sudo apt install docker.io
```

4. Обновление docker compose до v2 для всех пользователей:
```
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.28.1/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

*Официальная инструкция*: [docs.docker.com/compose/install/linux/#install-the-plugin-manually](https://docs.docker.com/compose/install/linux/#install-the-plugin-manually)

5. Создание пользователя для деплоя согласно [инструкции](./wiki/deploy.md)

6. Очистка неиспользуемых ресурсов Docker согласно [инструкции](./wiki/prune.md)

---

### Базовые сервисы

- [Traefik](./traefik/README.md)
- [Portainer](./portainer/README.md)
- [RabbitMQ](./rabbitmq/README.md)
- [Postgres](./postgres/README.md)
- [Centrifugo](./centrifugo/README.md)

---

### CI/CD Jenkins
- [Jenkins](./jenkins/README.md)
- [Dockerhub](./dockerhub/README.md)

### VPN
- [VPN](./vpn/README.md)
