from configparser import RawConfigParser

import aredis
import msgpack
from loguru import logger as log

DISCORD_OPTIONS = {'command_prefix': 'None', 'setupran': 'False', 'setupadmin': 'None', 'setupadmin_id': 0, 'admin_role_id': 0, 'admin_role': 'None', 'user_role_id': 0, 'user_role': 'None', 'pm_only': 'True', 'limit_to_channel': 'None', 'limit_to_channel_id': 0}

SERVER_OPTIONS = {'server_name': 'None', 'server_region': 'None', 'server_timezone': 'None', 'server_id': 0, 'server_slug': 'None', 'guild_name': 'None', 'faction': 'None', 'server_type': 'None', 'server_locale': 'None', 'server_region_name': 'None'}

WARCRAFTLOGS_OPTIONS = {"api_key": "None"}

BLIZZARD_OPTIONS = {'client_id': 'None', 'client_secret': 'None'}


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
            self.read_dict(msgpack.unpackb(read_config))
            await self._check_defaults()

    async def write(self):
        if len(self.redis.pool._available_connections) == 0 or not self.redis.connected:
            await self.redis.connect()
        await self.redis.redis.set(self.guild_id, msgpack.packb(self._sections))

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
