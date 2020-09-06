from configparser import ConfigParser
from requests import Session
from urllib import parse


class WCLClient:

    def __init__(self, url, api_key):
        self.url = url
        self.api_key = api_key
        self.session = Session()

    def _get(self, path, **kwargs):
        params = {"api_key": self.api_key}
        params.update(kwargs)
        url = parse.urljoin(self.url, path)
        return self.session.get(url, params=params)

    def guild(self, name, server, region, **params):
        path = "reports/guild/{}/{}/{}".format(name, server, region)
        llist = self._get(path, **params).json()
        return llist

    def parses(self, name, server, region, **params):
        path = "parses/character/{}/{}/{}".format(name, server, region)
        llist = self._get(path, **params).json()
        return llist

    def fights(self, code, **params):
        path = "report/fights/{}".format(code)
        llist = self._get(path, **params).json()
        return llist

    def tables(self, view, code, **params):
        path = "report/tables/{}/{}".format(view, code)
        llist = self._get(path, **params).json()
        return llist

    def events(self, view, code, **params):
        path = "report/events/{}/{}".format(view, code)
        llist = self._get(path, **params).json()
        return llist


class TSMClient:

    def __init__(self, url):
        self.url = url
        self.session = Session()

    def _get(self, path, **kwargs):
        params = kwargs
        url = parse.urljoin(self.url, path)
        return self.session.get(url, params=params)

    def get_item_data(self, itemid, server, faction, **params):
        path = f"items/{server.lower()}-{faction.lower()}/{itemid}"
        llist = self._get(path, **params).json()
        return llist

