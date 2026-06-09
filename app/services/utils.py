import os
import hmac
import hashlib
from cryptography.fernet import Fernet
from django.core.cache import cache


# 1. ЧТЕНИЕ СЕКРЕТОВ (5.6)
def get_env(key, default=None):
    """Достает ключи из .env файла"""
    return os.getenv(key, default)


# 2. НОРМАЛИЗАЦИЯ ТЕЛЕФОНА (5.7 Helpers)
def normalize_phone(phone):
    if not phone or str(phone).lower() == 'none': return ""
    clean = "".join(filter(str.isdigit, str(phone)))
    if len(clean) == 9: return '998' + clean
    return clean if len(clean) == 12 else ""


# 3. ШИФРОВАНИЕ И РАСШИФРОВКА (5.4)
def encrypt(data):
    if not data: return data
    key = get_env("ENCRYPTION_KEY").encode()
    return Fernet(key).encrypt(str(data).encode()).decode()


def decrypt(data):
    if not data: return data
    key = get_env("ENCRYPTION_KEY").encode()
    return Fernet(key).decrypt(str(data).encode()).decode()


# 4. ХЭШИРОВАНИЕ ЗАПРОСА (5.3)
def hash_request(data_string):
    secret = get_env("SECRET_KEY", "fallback-secret")
    return hmac.new(secret.encode(), data_string.encode(), hashlib.sha256).hexdigest()


# 5. КАСТОМНЫЙ RATE LIMITER (Защита от Брутфорса - 5.7)
def is_rate_limited(key, limit=5, timeout=60):
    """
    Проверяет, было ли сделано больше 'limit' запросов за 'timeout' секунд.
    """
    count = cache.get(key, 0)

    if count >= limit:
        return True  # Лимит исчерпан, блокируем!

    if count == 0:
        # Первый запрос, ставим счетчик на 1 и запускаем таймер на 60 секунд
        cache.set(key, 1, timeout=timeout)
    else:
        # Увеличиваем счетчик
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, count + 1, timeout=timeout)

    return False  # Всё ок, пропускаем