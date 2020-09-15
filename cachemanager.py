import aredis
from loguru import logger as log


class CacheManager:

    def __init__(self, redispool):
        self.redis = redispool


    async def 

    async def read(self):
        if len(self.redis.pool._available_connections) == 0 or not self.redis.connected:
            await self.redis.connect()
        read_config = await self.redis.redis.get(self.guild_id)
        if read_config is None:
            log.warning(f'Trying to read config entry from a missing guild id in database [{self.guild_id}], loading defaults')
            await self._check_defaults()
        else:
            self.read_dict(eval(read_config.decode()))
            await self._check_defaults()

    async def write(self):
        if len(self.redis.pool._available_connections) == 0 or not self.redis.connected:
            await self.redis.connect()
        await self.redis.redis.set(self.guild_id, simplejson.dumps(self._sections))

