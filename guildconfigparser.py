from asyncio import sleep
from configparser import RawConfigParser
import simplejson

import aredis
from loguru import logger as log


class RedisPool:

    def __init__(self, host, port, db, max_idle_time=30, idle_check_interval=0.1, max_connections=50):
        self.host = host
        self.port = port
        self.db = db
        self.max_idle_time = max_idle_time
        self.idle_check_interval = idle_check_interval
        self.max_connections = max_connections
        self.pool = aredis.ConnectionPool(host=host, port=port, db=db, max_connections=max_connections)
        self.redis = aredis.StrictRedis(connection_pool=self.pool)
        self.connected = False

    async def connect(self):
        while len(self.pool._available_connections) == 0 or not self.connected:
            try:
                await self.redis.ping()
            except:
                self.connected = False
                log.warning("Failed connection to Redis server, retrying...")
                await sleep(10)
            else:
                self.connected = True
                log.debug(f"Connection verified to Redis server [{self.host}:{self.port} DB:{self.db}]")

    async def disconnect(self):
        self.verified = False
        self.pool.disconnect()


class GuildConfigParser(RawConfigParser):

    def __init__(self, redis, guild_id):
        RawConfigParser.__init__(self)
        self.redis = redis
        self.guild_id = guild_id

    async def read(self):
        if len(self.redis.pool._available_connections) == 0 or not self.redis.connected:
            await self.redis.connect()
        read_config = await self.redis.redis.get(self.guild_id)
        if read_config is None:
            log.error(f'Trying to read config entry from a missing guild id in database [{self.guild_id}], loading defaults')
            await self.default()
        else:
            self.read_dict(eval(read_config.decode()))

    async def write(self):
        if len(self.redis.pool._available_connections) == 0 or not self.redis.connected:
            await self.redis.connect()
        await self.redis.redis.set(self.guild_id, simplejson.dumps(self._sections))

    async def default(self):
        self.add_section("discord")
        self.set("discord", "command_prefix", "?")
        self.set("discord", "admin_role_id", "None")
        self.set("discord", "admin_role", "None")
        self.set("discord", "user_role_id", "None")
        self.set("discord", "user_role", "None")
        self.set("discord", "pm_only", "False")
        self.set("discord", "limit_to_channel", "All")
        self.add_section("server")
        self.set("server", "server_name", "My Server Name")
        self.set("server", "server_region", "US")
        self.set("server", "server_timezone", "America/Los_Angeles")
        self.set("server", "guild_name", "My Guild Name")
        self.set("server", "faction", "Alliance")
        self.add_section("warcraftlogs")
        self.set("warcraftlogs", "api_key", "None")
        self.add_section("blizzard")
        self.set("blizzard", "client_id", "None")
        self.set("blizzard", "client_secret", "None")
        #self.add_section("tradeskillmaster")
        #self.set("tradeskillmaster", "fuzzy_search_threshold", "0.8")
        await self.write()
        log.debug(f'Wrote default configuration for guild id [{self.guild_id}]')
