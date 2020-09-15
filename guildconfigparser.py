from asyncio import sleep
from configparser import RawConfigParser

import aredis
import simplejson
from loguru import logger as log

DISCORD_OPTIONS = {'command_prefix': 'None', 'setupran': 'False', 'setupadmin': 'None', 'setupadmin_id': 0, 'admin_role_id': 0, 'admin_role': 'None', 'user_role_id': 0, 'user_role': 'None', 'pm_only': 'True', 'limit_to_channel': 'None', 'limit_to_channel_id': 0}

SERVER_OPTIONS = {'server_name': 'None', 'server_region': 'None', 'server_timezone': 'None', 'server_id': 0, 'server_slug': 'None', 'guild_name': 'None', 'faction': 'None', 'server_type': 'None', 'server_locale': 'None', 'server_region_name': 'None'}

WARCRAFTLOGS_OPTIONS = {"api_key": "None"}

BLIZZARD_OPTIONS = {'client_id': 'None', 'client_secret': 'None'}


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
            log.warning(f'Trying to read config entry from a missing guild id in database [{self.guild_id}], loading defaults')
            await self._check_defaults()
        else:
            self.read_dict(eval(read_config.decode()))
            await self._check_defaults()

    async def write(self):
        if len(self.redis.pool._available_connections) == 0 or not self.redis.connected:
            await self.redis.connect()
        await self.redis.redis.set(self.guild_id, simplejson.dumps(self._sections))

    async def _check_defaults(self):
        changes = False
        if not self.has_section("discord"):
            changes = True
            self.add_section("discord")
        for key, val in DISCORD_OPTIONS.items():
            if not self.has_option("discord", key):
                changes = True
                log.debug(f'Adding guildconfig missing option for [{self.guild_id}]: "discord", {key}, {val}')
                self.set("discord", key, val)

        if not self.has_section("server"):
            changes = True
            self.add_section("server")
        for key, val in SERVER_OPTIONS.items():
            if not self.has_option("server", key):
                changes = True
                log.debug(f'Adding guildconfig missing option for [{self.guild_id}]: "server", {key}, {val}')
                self.set("server", key, val)

        if not self.has_section("warcraftlogs"):
            changes = True
            self.add_section("warcraftlogs")
        for key, val in WARCRAFTLOGS_OPTIONS.items():
            if not self.has_option("warcraftlogs", key):
                changes = True
                log.debug(f'Adding guildconfig missing option for [{self.guild_id}]: "warcraftlogs", {key}, {val}')
                self.set("warcraftlogs", key, val)

        if not self.has_section("blizzard"):
            changes = True
            self.add_section("blizzard")
        for key, val in BLIZZARD_OPTIONS.items():
            if not self.has_option("blizzard", key):
                changes = True
                log.debug(f'Adding guildconfig missing option for [{self.guild_id}]: "blizzard", {key}, {val}')
                self.set("blizzard", key, val)

        if changes:
            await self.write()
            log.info(f'Updated configuration for guild [{self.guild_id}]')
