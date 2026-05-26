#tests/test_fund.py
import pytest
import allure

from api import get_accounts,apply_payment
from common import assert_success

@allure.feature("资金管理")
class TestFund:
    @allure.story("获取账户")
    @pytest.mark.P1
    def test_get_accounts(self):
        resp = get_accounts()

        #判断接口是通
        assert resp.status_code == 200

        #引入断言工具
        data = assert_success(resp)
        # 3.判断data中的账户数量
        assert len(data)> 0
        # 4.判断具体字段
        account = data[0]
        assert "account_no" in account
        assert "bank_name" in account

    @allure.story("付款管理")
    @pytest.mark.P0
    def test_apply_payment(self):
        resp = apply_payment("1001",
                             "1100002",
                             "招商银行",
                             "总公司资金池主账户",
                             5000,
                             "CNY",
                             "购买生活用品",
                             "公司报销")


        # 引入断言工具
        data = assert_success(resp,dict)

        assert "req_no" in data
        assert data["current_step"] == "manager"