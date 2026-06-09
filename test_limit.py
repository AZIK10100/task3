import requests
import time

# ИСПРАВЛЕННЫЙ URL
URL = "http://127.0.0.1:8000/rpc/"

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "transfer.confirm",
    "params": {
        "ext_id": "hacker-test-999",
        "otp": "000000"
    }
}

print("🚀 НАЧИНАЕМ АТАКУ ПОДБОРОМ ПАРОЛЯ...\n")

# Делаем 7 быстрых запросов
for i in range(1, 8):
    print(f"Попытка {i}...")

    response = requests.post(URL, json=payload)

    # Теперь ответ должен быть в правильном JSON формате
    print("Ответ сервера:", response.json())
    print("-" * 40)

    time.sleep(0.5)

print("✅ ТЕСТ ЗАВЕРШЕН!")
