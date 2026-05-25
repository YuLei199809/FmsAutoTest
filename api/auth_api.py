#api/auth_api.py
#认证模块接口封装：登录，登出，获取koten等

#1.导入请求工具
from config import http

def login(username,password):
    """
    登录接口
    :param username: 登录账号
    :param password: 登录密码
    :return:
    """
    body = {
        "username":username,
        "password":password
    }

    return http.post("/api/auth/login",json=body)


def logout(token):
    """
    退出登录
    :param token:认证密钥
    :return:
    """
    headers = {
        "Authorization":f"Bearer {token}"
    }

    return http.post("/api/auth/logout",headers=headers)

