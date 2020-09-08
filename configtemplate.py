
from aredisconfigparser import aRedisConfigParser


class GuildConfig(aRedisConfigParser):

    def __init__(self, guild_id):
        RawConfigParser.__init__(self)
        self.guild_id = guild_id

    def defaultconfig():
        
    
