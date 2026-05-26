# conftest.py
import pytest
from api import login
from config import http,USERNAME,PASSWORD

@pytest.fixture(scope="session", autouse=True)
def global_login():
    print("\n========== global_login fixture 开始执行 ==========")
    result = login(USERNAME, PASSWORD)
    print(f"登录状态码: {result.status_code}")
    print(f"登录响应体: {result.json()}")
    token = result.json()['data']['token']
    http.set_token(token)
    print(f"http 对象 id: {id(http)}")
    print(f"session headers: {dict(http.session.headers)}")
    print("========== global_login fixture 执行完毕 ==========")