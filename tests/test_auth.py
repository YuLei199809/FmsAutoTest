#tests/test_auth.py
import pytest

from api import login,get_accounts

@pytest.mark.P2
def test_login_success():
    resp = login("cashier01","123456")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["token"] is not None

@pytest.mark.P2
def test_login_fail():
    resp = login("admin","14124124")
    assert resp.status_code == 401

