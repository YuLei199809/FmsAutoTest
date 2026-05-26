#tests/test_auth.py
import pytest
import allure

from api import login,get_accounts
@allure.feature("认证模块")
class TestAuth:
    @allure.story("登录")
    @pytest.mark.P2
    def test_login_success(self):
        resp = login("cashier01","123456")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["token"] is not None

    @allure.story("退出")
    @pytest.mark.P2
    def test_login_fail(self):
        resp = login("admin","14124124")
        assert resp.status_code == 401

