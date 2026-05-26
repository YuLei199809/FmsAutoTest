#config/env.py
from common.http_client import HttpClient
from config.settings import config

BASE_URL = config["base_url"]
USERNAME = config["username"]
PASSWORD = config["password"]


#实例话化请求工具，全局唯一对象
http = HttpClient(BASE_URL)

TIMEOUT = 30

HEADERS = {
    "Content-Tpye":"application:json"
}

