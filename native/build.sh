#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

gcc -m64 -O0 -fno-stack-protector -no-pie -o ticker_validator ticker_validator.c

echo "Собрано: $(pwd)/ticker_validator"
echo
echo "Символы для эксплойта (адрес secret_backdoor может отличаться на"
echo "другой машине/версии gcc — пересчитайте через nm при необходимости):"
nm ticker_validator | grep -E "secret_backdoor|validate_ticker"
