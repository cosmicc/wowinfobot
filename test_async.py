import asyncio
import uvloop
import aredis
from aredis.connection import UnixDomainSocketConnection
from prettyprinter import pprint

pool = aredis.ConnectionPool(connection_class=UnixDomainSocketConnection, path='/tmp/redis-cache.sock', db=0)
redis = aredis.StrictRedis(connection_pool=pool)


async def speak_async():
    pprint(await redis.exists('news'))
    b = redis.cache('news')
    pprint(dir(b))

loop = asyncio.get_event_loop()
uvloop.install()
loop.run_until_complete(speak_async())
loop.close()
