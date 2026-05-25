#api/fund_api.py
from config import http

def get_accounts():
    """
    获取账户接口
    :return:
    """

    return http.get("/api/fund/accounts")

def apply_payment(from_account,to_account,to_bank,to_name,amount,currency,purpose,remark):
    """
    付款申请接口
    :param from_account:付款账户
    :param to_account:收款账户
    :param to_bank:收款银行
    :param to_name:收款名称
    :param amount:金额
    :param currency:币种
    :param purpose:付款用途
    :param remark:备注
    :return:
    """
    body = {
        "from_account":from_account,
        "to_account": to_account,
        "to_bank":to_bank,
        "to_name":to_name,
        "amount":amount,
        "currency":currency,
        "purpose":purpose,
        "remark":remark
    }
    return http.post("/api/fund/payment/apply",json=body)