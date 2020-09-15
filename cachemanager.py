from loguru import logger as log
import msgpack


async def getcache(redis, key):
    if await redis.redis.exists(key):
        log.trace(f'Cache HIT! for [{key}]')
        return msgpack.unpackb(await redis.redis.get(key))
    else:
        log.trace(f'Cache MISS! for [{key}]')
        return None


async def putcache(redis, key, value, exp):
    log.trace(f'Populating cache for [{key}] expires [{exp}]')
    await redis.redis.set(key, msgpack.packb(value), ex=exp)
