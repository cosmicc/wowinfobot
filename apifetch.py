import asyncio
from urllib import parse

import aiohttp
from loguru import logger as log


class WarcraftLogsAPI:

    def __init__(self, url, api_key):
        self.url = url
        self.api_key = api_key
        self.session = aiohttp.ClientSession()

    async def _get(self, path, **kwargs):
        params = {"api_key": self.api_key}
        params.update(kwargs)
        url = parse.urljoin(self.url, path)
        log.debug(f'WarLogsAPI Retreiving URL: {url}')
        try:
            async with self.session.get(url, params=params, timeout=5) as response:
                log.debug(f'WarLogsAPI HTTP Response: {response.status}')
                if response.status == 200:
                    log.debug(f'WarLogsAPI Returning JSON response')
                    return await response.json()
                else:
                    log.error(f'WarLogsAPI RETRIEVE ERROR! {url}')
                    return False
        except asyncio.exceptions.TimeoutError:
            log.error(f'WarLogsAPI Timeout Error!')
            return False

    async def guild(self, name, server, region, **params):
        path = "reports/guild/{}/{}/{}".format(name, server, region)
        return await self._get(path, **params)

    async def parses(self, name, server, region, **params):
        path = "parses/character/{}/{}/{}".format(name, server, region)
        return await self._get(path, **params)

    async def fights(self, code, **params):
        path = "report/fights/{}".format(code)
        return await self._get(path, **params)

    async def tables(self, view, code, **params):
        path = "report/tables/{}/{}".format(view, code)
        return await self._get(path, **params)

    async def events(self, view, code, **params):
        path = "report/events/{}/{}".format(view, code)
        return await self._get(path, **params)


class NexusAPI:

    def __init__(self, url):
        self.url = url
        self.session = aiohttp.ClientSession()

    async def _get(self, path, **kwargs):
        params = kwargs
        url = parse.urljoin(self.url, path)
        log.debug(f'NexusAPI Retreiving URL: {url}')
        try:
            async with self.session.get(url, params=params, timeout=5) as response:
                log.debug(f'NexusAPI HTTP Response: {response.status}')
                if response.status == 200:
                    log.debug(f'NexusAPI Returning JSON response')
                    return await response.json()
                else:
                    log.error(f'NexusAPI RETRIEVE ERROR! {url}')
        except asyncio.exceptions.TimeoutError:
            log.error(f'WarLogsAPI Timeout Error!')
            return False

    async def price(self, itemid, server, faction, **params):
        path = f"items/{server.lower()}-{faction.lower()}/{itemid}"
        return await self._get(path, **params)

    async def search(self, **params):
        path = f"search"
        return await self._get(path, **params)

    async def content(self, **params):
        path = f"content"
        return await self._get(path, **params)

    async def news(self, **params):
        path = f"news"
        return await self._get(path, **params)

    async def deals(self, server, **params):
        path = f"crafting/{server.lower()}/deals"
        return await self._get(path, **params)

    async def crafting(self, itemid, server, **params):
        path = f"crafting/{server.lower()}/{itemid}"
        return await self._get(path, **params)
