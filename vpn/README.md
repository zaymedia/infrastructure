[« Вернуться к инфраструктуре](../README.md)

---

### Инструкция по запуску VPN

1. Создать A-запись в DNS для поддомена: vpn
2. Скопировать все файлы из данного каталога на сервер в директорию ../home/vpn
3. Перейти в директорию ../home/vpn
4. Заменить zay.media на свой домен в файле docker-compose.yml
5. Заменить значения VPN_IPSEC_PSK, VPN_USER, VPN_PASSWORD на собственные в файле docker-compose.yml
6. Запустить контейнеры:
```
make init
```
7. Подключение на устройствах: https://github.com/hwdsl2/setup-ipsec-vpn/blob/master/docs/clients.md#ios

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
