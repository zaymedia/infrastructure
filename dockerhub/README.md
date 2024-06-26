[« Вернуться к инфраструктуре](../README.md)

---

### Инструкция по запуску Dockerhub

1. Создать A-запись в DNS для поддомена: dockerhub
2. Скопировать все файлы из данного каталога на сервер в директорию ../home/dockerhub
3. Перейти в директорию ../home/dockerhub
4. Заменить zay.media на свой домен в файле docker-compose.yml
5. Сгенерировать файл с авторизацией для dockerhub командой (указав свой логин и пароль вместо YOUR_LOGIN и YOUR_PASSWORD):
```
docker run registry:2.6 htpasswd -Bbn YOUR_LOGIN YOUR_PASSWORD > htpasswd
```
6. Запустить контейнеры:
```
make init
```

---

### Полезные команды
Перезапустить контейнеры:
```
make restart
```

Перезапустить контейнеры с обновлением:
```
make init
```

Остановить контейнеры:
```
make down
```

Очистить неиспользуемые файлы:
```
make clear
```
Очистить неиспользуемые файлы (если не помогает команда выше):
```
make clear-force
```
