#config/env.py
from common.http_client import HttpClient

BASE_URL = "http://127.0.0.1:8000"

#实例话化请求工具，全局唯一对象
http = HttpClient(BASE_URL)

TIMEOUT = 30

HEADERS = {
    "Content":"application:json"
}

