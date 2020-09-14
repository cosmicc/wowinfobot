from asyncio import sleep
from configparser import RawConfigParser

import aredis
import simplejson
from loguru import logger as log


def start_redis_pool(host, port, db, max_idle_time=30, idle_check_interval=0.1, max_connections=10):
    pool = aredis.ConnectionPool(host=host, port=port, db=db, max_connections=max_connections)
    return aredis.StrictRedis(connection_pool=pool)


class aRedisConfigParser(RawConfigParser):

    __is_connected__ = False

    def __init__(self, redis_pool):
        RawConfigParser.__init__(self)
        self.redis = redis_pool

    async def connect(self):
        while len(self.pool._available_connections) == 0 or not self.verified:
                try:
                    await self.redis.ping()
                except:
                    self.__is_connected__ = False
                    log.warning("Failed verifying connection to Redis server, retrying...")
                    await sleep(10)
                else:
                    self.__is_connected__ = True
                    self.verified = True
                    log.debug(f"Connection verified to Redis server [{self.host}:{self.port}]")

    async def disconnect(self):
        self.verified = False
        self.pool.disconnect()

    async def read(self, namespace):
        if not self.__is_connected__:
            await self.connect()
        config_dict = eval(await self.redis.get(namespace))
        self.read_dict(config_dict)

    async def write(self, namespace):
        if not self.__is_connected__:
            await self.connect()
        await self.redis.set(namespace, simplejson.dumps(self._sections))
