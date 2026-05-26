#tests/test_fund.py
import pytest

from api import get_accounts,apply_payment
from common import assert_success

@pytest.mark.P1
def test_get_accounts():
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

@pytest.mark.P0
def test_apply_payment():
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