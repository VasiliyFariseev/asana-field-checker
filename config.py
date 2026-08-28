# -*- coding: utf-8 -*-
"""Настройки Field Checker. Токен лежит здесь — репозиторий должен
быть ПРИВАТНЫМ, а архив раздаваться только личным сообщением."""
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ASANA_TOKEN = os.environ.get(
    "ASANA_TOKEN",
    "2/1188026399943634/1216300001925457:844eca7f6f48e52b018197b3153c28b3")
ASANA_BASE = "https://app.asana.com/api/1.0"
DEFAULT_PROJECTS = "1204015220636637"         # Expedition Team QA; можно несколько через запятую

# Какие поля проверяем. Ищутся по имени без учёта регистра;
# совпадение по вхождению, поэтому «FD: Version» найдёт и «FD:Version».
FIELD_A = "FD: Version"
FIELD_B = "FD Milestone"

# Сессия с ретраями и таймаутом: подвисший запрос не должен висеть вечно
_retry = Retry(total=3, backoff_factor=1.5,
               status_forcelist=(429, 500, 502, 503, 504),
               allowed_methods=("GET", "POST"))
_http = requests.Session()
_adapter = HTTPAdapter(max_retries=_retry)
_http.mount("https://", _adapter)
_orig_request = _http.request


def _request_with_timeout(method, url, **kwargs):
    kwargs.setdefault("timeout", (10, 60))
    return _orig_request(method, url, **kwargs)


_http.request = _request_with_timeout
requests.get = _http.get
requests.post = _http.post


def asana_headers() -> dict:
    return {"Authorization": f"Bearer {ASANA_TOKEN}",
            "Content-Type": "application/json"}
