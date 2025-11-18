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

---

Конфигурация клиента доступна внутри Docker-контейнера:
- /etc/ipsec.d/vpnclient.p12 (for Windows & Linux)
- /etc/ipsec.d/vpnclient.sswan (for Android)
- /etc/ipsec.d/vpnclient.mobileconfig (for iOS & macOS)

Скопировать нужную конфигурацию из Docker-контейнера на хост-машину:
```
docker cp vpn:/etc/ipsec.d/vpnclient.mobileconfig ./
```

1. Скачать нужную конфигурацию на устройство и открыть.
2. В macOS или iOS появится предупреждение: перейдите в Settings → Profiles (Профили), нажмите Install (Установить).
3. Подтвердите установку, следуя инструкциям.
4. После установки профиль появится в разделе Settings → VPN.
5. Выберите профиль и нажмите Connect
