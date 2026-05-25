# 断言工具

def assert_success(resp,data_type=list,status_code=200):
    #接口是否通
    assert resp.status_code == status_code

    #判断返回结构
    body = resp.json()
    assert "code" in body
    assert "data" in body

    #判断返回代码
    assert body['code'] == 200

    #判断数据主体数据类型
    assert isinstance(body["data"],data_type)

    return body["data"] #返回数据主体内容