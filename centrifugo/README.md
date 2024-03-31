[« Вернуться к инфраструктуре](../README.md)

---

### Инструкция по запуску Centrifugo

1. Создать A-запись в DNS для поддомена: realtime
2. Скопировать все файлы из данного каталога на сервер в директорию ../home/centrifugo
3. Перейти в директорию ../home/centrifugo
4. Заменить zay.media на свой домен в файле docker/config.json
5. Заполнить данные для полей token_hmac_secret_key, admin_password, admin_secret, api_key в файле docker/config.json
6. Заменить zay.media на свой домен в файле docker-compose.yml
7. Запустить контейнеры:
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
