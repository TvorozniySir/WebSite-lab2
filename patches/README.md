# Патчи

```bash
patch -p1 < patches/01-ssti-rce.patch
patch -p1 < patches/02-jwt-alg-none.patch
patch -p1 < patches/03-buffer-overflow.patch
bash native/build.sh   # пересборка native-сервиса обязательна после патча №3
```

Проверка, что патчи реально закрыли дыры — прогнать эксплойты заново:
```bash
python exploits/exploit_1_ssti_rce.py       # payload больше не исполняется
python exploits/exploit_2_jwt_forgery.py    # "unsupported alg" вместо списка юзеров
python exploits/exploit_3_buffer_overflow.py  # "REJECTED: ticker too long" вместо BACKDOOR REACHED
```

Я лично применил и проверил каждый патч на чистой копии проекта —
каждая уязвимость после патча закрывается, легитимный функционал
(обычный тикер, обычный логин, обычное био) продолжает работать.
