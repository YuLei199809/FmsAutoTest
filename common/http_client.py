#common/http_client.py
import requests
import logging

logger = logging.getLogger(__name__)

class HttpClient:
    def __init__(self,base_url:str):
        self.base_url = base_url
        self.session = requests.Session()
        self.url = {}

    def client(self,method:str,path:str,**kwargs):
        self.url = self.base_url+path

        result = self.session.request(method,self.url,**kwargs)

        return result

    def get(self,path,**kwargs):
        return self.client("GET",path,**kwargs)

    def post(self,path,**kwargs):
        return self.client("POST",path,**kwargs)

    def set_token(self,token):
        self.session.headers.update({"authorization" : f"Bearer {token}"})



