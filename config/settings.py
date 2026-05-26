#config/settings

import os

ENV = os.getenv("ENV","dev")

_CONFIG = {
    "dev" : {
        "base_url":"http://127.0.0.1:8000",
        "username":"cashier01",
        "password":"123456"
    },
    "test": {
        "base_url":"http://127.0.0.1:8001",
        "username":"cashier01",
        "password":"123456"
    }
}
if ENV not in _CONFIG:
    raise ValueError(f"未知环境:{ENV},可选:{_CONFIG}")

config = _CONFIG[ENV]