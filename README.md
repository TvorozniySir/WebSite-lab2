# hackwebapp — Лабораторная работа №2

Трейдинг-платформа на Flask (регистрация, email-подтверждение, 2FA,
ордера, портфель) с тремя намеренными уязвимостями: **SSTI → RCE**,
**JWT `alg:none` forgery**, **Stack Buffer Overflow → RCE**.

Подробный разбор каждой — [`VULNERABILITIES.md`](VULNERABILITIES.md).

## Запуск (часть 1)

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
bash native/build.sh          # собрать уязвимый нативный сервис (нужен gcc)
python app.py                 # http://127.0.0.1:5000
```

Регистрация → `/register` → QR в TOTP-приложение → ссылка подтверждения
email выводится **в консоль сервера** (реальная почта не используется)
→ `/login`.

Админ-доступ: `python set_admin.py <username>`.

## Эксплойты (часть 2)

```bash
pip install -r exploits/requirements.txt
python exploits/exploit_1_ssti_rce.py
python exploits/exploit_2_jwt_forgery.py
python exploits/exploit_3_buffer_overflow.py
```
Подробнее — [`exploits/README.md`](exploits/README.md).

## Патчи (часть 3)

```bash
patch -p1 < patches/01-ssti-rce.patch
patch -p1 < patches/02-jwt-alg-none.patch
patch -p1 < patches/03-buffer-overflow.patch
bash native/build.sh
```
Подробнее — [`patches/README.md`](patches/README.md).

## Структура

```
app.py, models.py, forms.py, email_utils.py   основное приложение
auth_jwt.py                                    самописный JWT (уязвимость №2)
native/ticker_validator.c, build.sh            нативный сервис (уязвимость №3)
templates/, static/                            UI
exploits/                                       часть 2 — эксплойт-скрипты
patches/                                        часть 3 — diff-патчи
VULNERABILITIES.md                              разбор всех трёх уязвимостей
```
