import requests
import urllib3


class RequestUtil:
    DEFAULT_TIMEOUT = 10

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def all_send_request(self, method, url, timeout=DEFAULT_TIMEOUT, **kwargs):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        res = self.session.request(method=method, url=url, timeout=timeout, **kwargs)
        res.raise_for_status()
        return res
