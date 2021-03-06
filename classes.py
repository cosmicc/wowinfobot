from asyncio import sleep

import aredis
from aredis.connection import UnixDomainSocketConnection

from loguru import logger as log
from cachemanager import getcache, putcache
from constants import BOSSREF, ROLES, RZONE, SPECROLES
from timefunctions import convert_time


class RedisPool:

    def __init__(self, socket, host, port, db, max_idle_time=30, idle_check_interval=0.1, max_connections=50):
        self.socket = socket
        self.host = host
        self.port = port
        self.db = db
        self.max_idle_time = max_idle_time
        self.idle_check_interval = idle_check_interval
        self.max_connections = max_connections
        self.pool = None
        if self.socket != "" and (self.socket).lower() != "none":
            self.connection = 'socket'

            self.pool = aredis.ConnectionPool(connection_class=UnixDomainSocketConnection, path=self.socket, db=self.db)
        else:
            self.connection = 'tcp'
            self.pool = aredis.ConnectionPool(host=self.host, port=self.port, db=self.db, max_connections=self.max_connections)
        self.redis = aredis.StrictRedis(connection_pool=self.pool)
        self.connected = False

    async def connect(self):
            while len(self.pool._available_connections) == 0 or not self.connected:
                try:
                    await self.redis.ping()
                except:
                    self.connected = False
                    log.exception("Failed connection to Redis server, retrying...")
                    await sleep(10)
                else:
                    self.connected = True
                    if self.connection == 'socket':
                        log.debug(f"{self.connection.capitalize()} connection verified to Redis socket [{self.socket}]")
                    else:
                        log.debug(f"{self.connection.capitalize()} connection verified to Redis server [{self.host}:{self.port} DB:{self.db}]")

    async def disconnect(self):
        self.verified = False
        if self.pool is not None:
            self.pool.disconnect()


class Item:

    def __init__(self, server, faction, itemid):
        self.name = None
        self.exists = False
        self.id = itemid
        self.icon = None
        self.server = server
        self.faction = faction
        self.tags = []
        self.requiredlevel = 'Not Available'
        self.level = 'Not Available'
        self.sellprice = 'Not Available'
        self.vendorprice = 'Not Available'
        self.lastupdate = 'Not Available'
        self.current_marketvalue = 'Not Available'
        self.current_historicalvalue = 'Not Available'
        self.current_minbuyout = 'Not Available'
        self.current_auctions = 'Not Available'
        self.current_quantity = 'Not Available'
        self.previous_marketvalue = 'Not Available'
        self.previous_historicalvalue = 'Not Available'
        self.previous_minbuyout = 'Not Available'
        self.previous_auctions = 'Not Available'
        self.previous_quantity = 'Not Available'
        self.tooltip = []

    async def fetch(self, tsmclient):
        itemdata = await tsmclient.price(self.id, self.server.lower(), self.faction.lower())
        if 'error' in itemdata:
            return itemdata
        if len(itemdata) == 0:
            return [{'error': 400}]
        else:
            self.exists = True
            self.name = itemdata['name']
            self.icon = itemdata['icon']
            self.tags = itemdata['tags']
            self.requiredlevel = itemdata['requiredLevel']
            self.level = itemdata['itemLevel']
            self.sellprice = itemdata['sellPrice']
            self.vendorprice = itemdata['vendorPrice']
            self.lastupdate = itemdata['stats']['lastUpdated']
            if itemdata['stats']['current'] is not None:
                self.current_marketvalue = itemdata['stats']['current']['marketValue']
                self.current_historicalvalue = itemdata['stats']['current']['historicalValue']
                self.current_minbuyout = itemdata['stats']['current']['minBuyout']
                self.current_auctions = itemdata['stats']['current']['numAuctions']
                self.current_quantity = itemdata['stats']['current']['quantity']
            if itemdata['stats']['previous'] is not None:
                self.previous_marketvalue = itemdata['stats']['previous']['marketValue']
                self.previous_historicalvalue = itemdata['stats']['previous']['historicalValue']
                self.previous_minbuyout = itemdata['stats']['previous']['minBuyout']
                self.previous_auctions = itemdata['stats']['previous']['numAuctions']
                self.previous_quantity = itemdata['stats']['previous']['quantity']
                self.tooltip = itemdata['tooltip']
            return itemdata


class Player:

    async def filter_last_encounters(self, npl):
        for entry in npl:
            if entry['startTime'] > min(self.edl):
                if entry['reportID'] in self.tpl:
                    if self.tpl[entry["reportID"]] in self.edl:
                        del self.edl[self.tpl[entry["reportID"]]]
                    if entry["reportID"] in self.tpl:
                        del self.tpl[entry["reportID"]]
                    self.edl.update({entry["startTime"]: entry})
                    self.tpl.update({entry["reportID"]: entry["startTime"]})
                else:
                    self.edl.update({entry["startTime"]: entry})
                    self.tpl.update({entry["reportID"]: entry["startTime"]})
                    if len(self.edl) > 5:
                        del self.edl[min(self.edl)]

    def __init__(self, gconfig, aclient, rediscache, parseexp, tableexp, playername):
        self.playername = playername.capitalize()
        self.exists = False
        self.parseexp = int(parseexp)
        self.tableexp = int(tableexp)
        self.rediscache = rediscache
        self.playerclass = "Not Available"
        self.playerspec = "Not Available"
        self.playerrole = "Not Available"
        self.totalencounters = 0
        self.gearlevel = 0
        self.mccount = 0
        self.bwlcount = 0
        self.zgcount = 0
        self.onycount = 0
        self.aq20count = 0
        self.aq40count = 0
        self.lastrank = 0
        self.lastpercent = 0
        self.gearlist = []
        self.geardate = "0"
        self.edl = {0: 0}
        self.tpl = {0: 0}
        self.client = aclient
        self.guildconfig = gconfig
        self.timezone = gconfig.get("server", "server_timezone")

    async def fetch(self):
        for kkey, vval in RZONE.items():
            parselist = await getcache(self.rediscache, f'{self.playername}-{self.guildconfig.get("server", "server_id")}-{kkey}')
            if parselist is None:
                parselist = await self.client.parses(self.playername, self.guildconfig.get("server", "server_name").title(), self.guildconfig.get("server", "server_region").upper(), zone=kkey)
                await putcache(self.rediscache, f'{self.playername}-{self.guildconfig.get("server", "server_id")}-{kkey}', parselist, 60 * self.parseexp)
            if len(parselist) > 0:
                if 'error' in parselist[0]:
                    self.exists = False
                    return parselist
                self.totalencounters = self.totalencounters + len(parselist)
                if kkey == 1000:
                    self.mccount = self.mccount + len(parselist)
                elif kkey == 1001:
                    self.onycount = self.onycount + len(parselist)
                elif kkey == 1002:
                    self.bwlcount = self.bwlcount + len(parselist)
                elif kkey == 1003:
                    self.zgcount = self.zgcount + len(parselist)
                elif kkey == 1004:
                    self.aq20count = self.aq20count + len(parselist)
                elif kkey == 1005:
                    self.aq40count = self.aq40count + len(parselist)
                await self.filter_last_encounters(parselist)
        if self.totalencounters > 0:
            self.exists = True
            self.lastencounters = sorted(self.edl.items())
            for encounter in self.lastencounters:
                if encounter[1] != 0:
                    if 'class' in encounter[1] and self.playerclass == "Not Available":
                        self.playerclass = encounter[1]['class']
                    if 'spec' in encounter[1] and self.playerspec == "Not Available":
                        if encounter[1]['spec'] not in ROLES:
                            self.playerspec = encounter[1]['spec']
                        else:
                            self.playerrole = encounter[1]['spec']

                    reporttable = await getcache(self.rediscache, f'tables-{encounter[1]["reportID"]}')
                    if reporttable is None:
                        reporttable = await self.client.tables('casts', encounter[1]['reportID'], start=0, end=18000)
                        await putcache(self.rediscache, f'tables-{encounter[1]["reportID"]}', reporttable, 60 * self.tableexp)

                    for entry in reporttable['entries']:
                        if entry['name'] == self.playername:
                            if 'spec' in entry and self.playerspec == "Not Available":
                                self.playerspec = entry['spec']
                            if 'icon' in entry and self.playerspec == "Not Available" and len(entry['icon'].split('-')) == 2:
                                self.playerclass = entry['icon'].split('-')[0]
                                self.playerspec = entry['icon'].split('-')[1]
                            if 'class' in entry and self.playerclass == "Not Available":
                                self.playerclass = entry['class']
                            if 'itemLevel' in entry and self.gearlevel == 0:
                                self.gearlevel = entry['itemLevel']
                            if 'gear' in entry:
                                if len(entry['gear']) > 1:
                                    zone = BOSSREF[encounter[1]['encounterName']]
                                    if zone == 1005:
                                        self.gearlist = entry['gear']
                                        self.geardate = convert_time(encounter[1]['startTime'], dateonly=True, tz=self.timezone)
                                    elif len(self.gearlist) < 1:
                                        self.gearlist = entry['gear']
                                        self.geardate = convert_time(encounter[1]['startTime'], dateonly=True, tz=self.timezone)
            self.lastencounter = self.lastencounters[len(self.lastencounters) - 1][1]
            if self.playerrole == "Not Available" and self.playerspec.lower() in SPECROLES:
                self.playerrole = SPECROLES[self.playerspec.lower()]
            return parselist
