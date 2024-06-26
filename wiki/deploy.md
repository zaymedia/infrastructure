[« Вернуться к инфраструктуре](../README.md)

---

### Создание пользователя для деплоя

1. Создать пользователя "deploy" (без пароля, вход только по публичному ключу):
```
sudo useradd -m -G sudo,docker deploy
```

2. Выдать пользователю "deploy" права на запись в директорию "/home":
```
sudo chown deploy:deploy /home
sudo chmod 700 /home
```

3. Переключиться на пользователя "deploy":
```
sudo su deploy
```

4. Создать папку ".ssh" и файл "authorized_keys" для пользователя "deploy":
```
mkdir ~/.ssh
touch ~/.ssh/authorized_keys
```

5. Скопировать свой публичный RSA ключ в файл "authorized_keys". Это можно сделать с помощью команды:
```
nano ~/.ssh/authorized_keys
```
Откроется текстовый редактор, в котором нужно вставить свой публичный ключ и сохранить изменения.<br>
Локально публичный ключ находится в папке: ~/.ssh (файл id_rsa.pub)

6. Установить права доступа к папке ".ssh" и файлу "authorized_keys":
```
chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
```

7. Выйти из под пользователя
```
exit
```

8. В CI/CD сервисах для деплоя через RSA ключ необходимо указывать приватный ключ (файл id_rsa)
