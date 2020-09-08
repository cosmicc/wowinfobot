#!/usr/bin/env python3.8
import signal
import traceback
from configparser import ConfigParser
from datetime import datetime
from math import trunc
from numbers import Number
from os import _exit, path, stat
from sys import exit

import discord
from discord.ext import commands
from loguru import logger as log
from prettyprinter import pprint
from pytz import timezone

from apifetch import NexusAPI, WarcraftLogsAPI
from processlock import PLock
from guildconfigparser import GuildConfigParser, RedisPool

configfile = '/etc/wowinfobot.cfg'
signals = (0, 'SIGHUP', 'SIGINT', 'SIGQUIT', 4, 5, 6, 7, 8, 'SIGKILL', 10, 11, 12, 13, 14, 'SIGTERM')


def signal_handler(signal, frame):
    log.warning(f'Termination signal [{signals[signal]}] caught. Closing web sessions...')
    wclclient.close()
    tsmclient.close()
    log.info(f'Exiting.')
    exit(0)


signal.signal(signal.SIGTERM, signal_handler)  # Graceful Shutdown
signal.signal(signal.SIGHUP, signal_handler)  # Reload/Restart
signal.signal(signal.SIGINT, signal_handler)  # Hard Exit
signal.signal(signal.SIGQUIT, signal_handler)  # Hard Exit

processlock = PLock()
processlock.lock()

if not path.exists(configfile) or stat(configfile).st_size == 0:
    log.error(f"Config file: {configfile} doesn't exist or is empty. Exiting.")
    exit(1)

configdata = ConfigParser()
configdata.read(configfile)

configtemplate = {'general': ['loglevel', 'logfile'], 'server': ['server_name', 'server_region', 'server_timezone', 'guild_name', 'faction'], 'discord': ['command_prefix', 'api_key'], 'warcraftlogs_api': ['api_url', 'api_key'], 'blizzard_api': ['api_url', 'client_id', 'client_secret'], 'tsm_api': ['api_url', 'fuzzy_search_threshold']}

for section, options in configtemplate.items():
    if not configdata.has_section(section):
        log.error(f'Error: Missing configuration section {section} in config file: {configfile}. Exiting.')
        exit(1)
    else:
        for option in options:
            if not configdata.has_option(section, option):
                log.error(f'Error: Missing config option {option} in {section} in config file: {configfile}. Exiting.')
                exit(1)

logfile = configdata.get("general", "logfile")
loglevel = configdata.get("general", "loglevel")
redis_host = configdata.get("general", "redis_host")
redis_port = configdata.get("general", "redis_port")
redis_db = configdata.get("general", "redis_db")
server = configdata.get("server", "server_name").capitalize()
region = configdata.get("server", "server_region").upper()
servertimezone = configdata.get("server", "server_timezone")
guild = configdata.get("server", "guild_name").capitalize()
faction = configdata.get("server", "faction").capitalize()
command_prefix = configdata.get("discord", "command_prefix")
discordkey = configdata.get("discord", "api_key")
bliz_url = configdata.get("blizzard_api", "api_url")
bliz_id = configdata.get("blizzard_api", "client_id")
bliz_secret = configdata.get("blizzard_api", "client_secret")
wcl_api = configdata.get("warcraftlogs_api", "api_key")
wcl_url = configdata.get("warcraftlogs_api", "api_url")
tsm_url = configdata.get("tsm_api", "api_url")
search_threshold = configdata.get("tsm_api", "fuzzy_search_threshold")

log.debug(f'System configuration loaded successfully from {configfile}')

log.add(sink=str(logfile), level=loglevel, buffering=1, enqueue=True, backtrace=True, diagnose=True, serialize=False, delay=False, rotation="5       MB", retention="1 month", compression="tar.gz")

log.debug(f'Logfile started: {logfile}')

bot = commands.Bot(command_prefix=command_prefix, case_insensitive=True)
bot.remove_command("help")
log.debug('Discord class initalized')

redis = RedisPool(redis_host, redis_port, redis_db)
bot.loop.create_task(redis.connect())
wclbot = WarcraftLogsAPI(wcl_url, wcl_api)
log.debug('WarcraftLogsAPI class initalized')
tsmbot = NexusAPI(tsm_url)
log.debug('NexusAPI class initalized')

SUCCESS_COLOR = 0x00FF00
FAIL_COLOR = 0xFF0000
INFO_COLOR = 0x0088FF
HELP_COLOR = 0xFF8800
GEAR_ORDER = {0: 'Head', 1: 'Neck', 2: 'Shoulders', 3: 'Shirt', 4: 'Chest', 5: 'Belt', 6: 'Legs', 7: 'Boots', 8: 'Bracers', 9: 'Hands', 10: 'Ring', 11: 'Ring', 12: 'Trinket', 13: 'Trinket', 14: 'Back', 15: 'Main Hand', 16: 'Off-Hand', 17: 'Ranged', 18: 'Tabard'}

item_quality = {1: 'Common', 2: 'Uncommon', 3: 'Rare', 4: 'Epic', 5: 'Legendary', 6: 'Artifact'}

ROLES = ['Tank', 'Healer', 'DPS']

RZONE = {1005: "Ahn'Qiraj 40", 1002: "Blackwing Lair", 1004: "Ahn'Qiraj 20", 1000: "Molten Core", 1003: "Zul'Gurub", 1001: "Onyxia"}

BOSSREF = {'Onyxia': 1001, 'Ragnaros': 1000, 'Lucifron': 1000, 'Magmadar': 1000, 'Gehennas': 1000, 'Garr': 1000, 'Baron Geddon': 1000, 'Shazzrah': 1000, 'Sulfuron Harbinger': 1000, 'Golemagg the Incinerator': 1000, 'Majordomo Executus': 1000, 'Ossirian the Unscarred': 1004, 'Ayamiss the Hunter': 1004, 'Buru the Gorger': 1004, 'Moam': 1004, 'General Rajaxx': 1004, 'Kurinnaxx': 1004, 'Nefarian': 1002, 'Chromaggus': 1000, "Jin'do the Hexxer": 1003, 'High Priest Thekal': 1003, "C'Thun": 1005, 'Ouro': 1005, 'Hakkar': 1003, 'Flamegor': 1002, 'Ebonroc': 1002, 'Princess Huhuran': 1005, 'The Prophet Skeram': 1005, 'Firemaw': 1002, 'Broodlord Lashlayer': 1002, 'Vaelastrasz the Corrupt': 1002}

BZONE = {1001: 1, 1003: 9, 1000: 10, 1004: 6, 1002: 8, 1005: 9}

intervals = (
    ("years", 31536000),
    ("months", 2592000),
    # ('weeks', 604800),  # 60 * 60 * 24 * 7
    ("days", 86400),  # 60 * 60 * 24
    ("hours", 3600),  # 60 * 60
    ("minutes", 60),
    ("seconds", 1),
)


def epochtz(epoch, servertimezone):
    fixedepoch = int(str(epoch)[:10])
    date_obj = datetime.fromtimestamp(fixedepoch)
    date_obj = timezone('UTC').localize(date_obj)
    date_obj = date_obj.astimezone(timezone(servertimezone))
    tzepoch = date_obj.timestamp()
    return (int(tzepoch))


def convert_time(dtime, timeonly=False, dateonly=False):
    if timeonly:
        return datetime.fromtimestamp(epochtz(dtime)).strftime('%-I:%M%p')
    elif dateonly:
        return datetime.fromtimestamp(epochtz(dtime)).strftime('%m/%d/%y')
    else:
        return datetime.fromtimestamp(epochtz(dtime)).strftime('%m/%d/%y %-I:%M%p')


def fix_item_time(rawtime, servertimezone):
    date_obj = datetime.strptime(rawtime, '%Y-%m-%dT%H:%M:%S.000Z')
    date_obj = timezone('UTC').localize(date_obj)
    date_obj = date_obj.astimezone(timezone(servertimezone))
    return date_obj.strftime('%m-%d-%y %I:%M %p')


def fix_news_time(rawtime, servertimezone):
    date_obj = datetime.strptime(rawtime, '%a, %d %b %Y %H:%M:%S -0500')
    date_obj = timezone('America/New_York').localize(date_obj)
    date_obj = date_obj.astimezone(timezone(servertimezone))
    return date_obj.strftime('%A, %b %d, %Y')


def truncate_float(number, digits):
    if not isinstance(number, (float, str)):
        number = float(number)
    if not isinstance(digits, int):
        raise TypeError(f"Digits value must be type int, not {type(digits)}")
    if isinstance(number, str):
        number = float(number)
    stepper = 10.0 ** abs(digits)
    return trunc(stepper * number) / stepper


def elapsedTime(start_time, stop_time, append=False):
    result = []
    if start_time > stop_time:
        seconds = int(start_time) - int(stop_time)
    else:
        seconds = int(stop_time) - int(start_time)
    granularity = 2
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip("s")
            result.append("{} {}".format(int(value), name))
    if append:
        return ", ".join(result[:granularity]) + f" {append}"
    else:
        return ", ".join(result[:granularity])


def convertprice(rawprice):
    if rawprice is None:
        return 'Not Available'
    if rawprice == 'Not Available':
        return 'Not Available'
    if rawprice < 100:
        return f'{rawprice}c'
    elif rawprice >= 100 and rawprice < 10000:
        silver = int(str(rawprice)[:-2])
        copper = int(str(rawprice)[-2:])
        return f'{silver}s {copper}c'
    elif rawprice >= 10000:
        silver = int(str(rawprice)[:-2])
        silver = int(str(silver)[-2:])
        copper = int(str(rawprice)[-2:])
        gold = int(str(rawprice)[:-4])
        return f'{gold}g {silver}s {copper}c'


async def user_info(ctx):
    if type(ctx.message.channel) == discord.channel.DMChannel:
        for guild in bot.guilds:
            member = discord.utils.get(guild.members, id=ctx.author.id)
            if member:
                is_admin_role = False
                is_user_role = False
                guildconfig = GuildConfigParser(redis, guild.id)
                await guildconfig.read()
                admin_id = guildconfig.get("discord", "admin_role_id")
                user_id = guildconfig.get("discord", "user_role_id")
                for role in member.roles:
                    if role.id == admin_id:
                        is_admin_role = True
                    if role.id == user_id:
                        is_user_role = True
                return {'user_id': ctx.author.id, 'user_name': ctx.author.name, 'guild_id': guild.id, 'channel': 'DMChannel', 'is_member': True, 'is_user_role': is_user_role, 'is_admin_role': is_admin_role}
            else:
                return {'user_id': ctx.author.id, 'user_name': ctx.author.name, 'guild_id': None, 'channel': 'DMChannel', 'is_member': False, 'is_user_role': False, 'is_admin_role': False}

    else:
        is_admin_role = False
        is_user_role = False
        guildconfig = GuildConfigParser(redis, ctx.author.guild.id)
        await guildconfig.read()
        admin_id = guildconfig.get("discord", "admin_role_id")
        user_id = guildconfig.get("discord", "user_role_id")
        member = discord.utils.get(ctx.author.guild.members, id=ctx.author.id)
        for role in member.roles:
            if role.id == admin_id:
                is_admin_role = True
            if role.id == user_id:
                is_user_role = True
        return {'user_id': ctx.author.id, 'user_name': ctx.author.name, 'guild_id': ctx.author.guild.id, 'channel': ctx.message.channel.id, 'is_member': True, 'is_user_role': is_user_role, 'is_admin_role': is_admin_role}


async def is_admin(ctx):
    admin = False
    memcount = 0
    if type(ctx.message.channel) == discord.channel.DMChannel:
        for guild in bot.guilds:
            if discord.utils.get(guild.members, id=ctx.author.id):
                memcount = memcount + 1
                pprint(guild.roles)
                if discord.utils.get(guild.roles, id=644205730395586570):
                    admin = True
                # print(discord.utils.get(guild.members, id=ctx.author.id))

            # the member is in the server, do something #
            else:
                # the member is not in the server, do something #
                pass
        if memcount != 1:
            log.warning(f'PM admin [ctx.author.name] auth failed (Found on {memcount} Servers)')
            # PM to tell them they are admins on multiple servers
            return False
        else:
            if admin:
                return True
            else:
                return False
    else:
        if ctx.member.roles.has(644205730395586570):
            return True
        else:
            return False


def filter_details(name, tags, labels):
    details = []
    for line in labels:
        label = line['label']
        if label != 'Sell Price:' and not label.startswith('Item Level') and not label.startswith('Requires Level') and label not in tags and label != name:
            details.append(label)
    return details


class Item:

    def __init__(self, guildid, itemid):
        self.name = None
        self.exists = False
        self.id = itemid
        self.icon = None
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

    async def fetch(self):
        itemdata = await tsmbot.price(self.id, server.lower(), faction.lower())
        if not itemdata:
            return False
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
            return True


class Player:

    async def filter_last_encounters(self, npl):
        for entry in npl:
            if epochtz(entry['startTime']) > min(self.edl):
                if entry['reportID'] in self.tpl:
                    del self.edl[self.tpl[entry["reportID"]]]
                    del self.tpl[entry["reportID"]]
                    self.edl.update({epochtz(entry["startTime"]): entry})
                    self.tpl.update({entry["reportID"]: epochtz(entry["startTime"])})
                else:
                    self.edl.update({epochtz(entry["startTime"]): entry})
                    self.tpl.update({entry["reportID"]: epochtz(entry["startTime"])})
                    if len(self.edl) > 5:
                        del self.edl[min(self.edl)]

    def __init__(self, playername):
        self.playername = playername.capitalize()
        self.exists = False
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

    async def fetch(self):
        for kkey, vval in RZONE.items():
            parselist = await wclbot.parses(self.playername, server, region, zone=kkey)
            if len(parselist) != 0 and 'error' not in parselist:
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
                    reporttable = await wclbot.tables('casts', encounter[1]['reportID'], start=0, end=18000)
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
                                        self.geardate = convert_time(encounter[1]['startTime'], dateonly=True)
                                    elif len(self.gearlist) < 1:
                                        self.gearlist = entry['gear']
                                        self.geardate = convert_time(encounter[1]['startTime'], dateonly=True)
            self.lastencounter = self.lastencounters[len(self.lastencounters) - 1][1]
            return True
        else:
            return None


@bot.event
async def on_ready():
        log.log("SUCCESS", f"Discord logged in as {bot.user.name} id {bot.user.id}")
        activity = discord.Game(name="Type ?help")
        try:
            await bot.change_presence(status=discord.Status.online, activity=activity)
        except:
            log.error("Exiting")


async def fight_data(fid):
    a = await wclbot.fights(fid)
    kills = 0
    wipes = 0
    size = 0
    for key, value in a.items():
        if key == 'fights':
            for each in value:
                if 'kill' in each:
                    if each['kill']:
                        kills = kills + 1
                        lastboss = each['name']
                        size = each['size']
                    if not each['kill']:
                        wipes = wipes + 1
    return kills, wipes, size, lastboss


def logcommand(ctx):
    if type(ctx.message.channel) == discord.channel.DMChannel:
        dchan = "Direct Message"
    else:
        dchan = ctx.message.channel
    log.log("INFO", f"Responding to [{ctx.message.content}] request from [{ctx.message.author}] in [#{dchan}]")
    return True


async def messagesend(ctx, embed, allowgeneral=False, reject=True, adminonly=False, rootonly=False):
    try:
        if type(ctx.message.channel) == discord.channel.DMChannel:
            return await ctx.message.author.send(embed=embed)
        # elif str(ctx.message.channel) != "bot-channel" or (not allowgeneral and str(ctx.message.channel) == "general"):
        # role = str(discord.utils.get(ctx.message.author.roles, name="admin"))
            # if role != "admin":
            #    await ctx.message.delete()
            # if reject and role != "admin":
            #    rejectembed = discord.Embed(description=rejectmsg, color=HELP_COLOR)
            #    return await ctx.message.author.send(embed=rejectembed)
            # elif role != "admin":
            #    return await ctx.message.author.send(embed=embed)
            # else:
        #    return await ctx.message.channel.send(embed=embed)
        else:
            return await ctx.message.channel.send(embed=embed)
    except:
        log.exception("Critical error in message send")


@bot.event
async def on_error(event, *args, **kwargs):
    message = args[0]
    log.error(traceback.format_exc())
    await bot.send_message(message.channel, "error")


'''
@bot.event
async def on_command_error(ctx, error):
    try:
        if isinstance(error, commands.CommandNotFound):
            log.warning(f"Invalid command [{ctx.message.content}] sent from [{ctx.message.author}]")
            msg = f"Command **`{ctx.message.content}`** does not exist.  **`{command_prefix}help`** for a list and description of all the commands."
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(ctx, embed, allowgeneral=False, reject=False)
        elif isinstance(error, commands.CheckFailure):
            log.warning(f"discord check failed: {error}")
            embed = discord.Embed(description="**An error has occurred, contact Arbin.**", color=FAIL_COLOR)
            # await messagesend(ctx, embed, allowgeneral=True, reject=False)
        else:
            log.exception(f"discord bot error for {ctx.message.author}: {ctx.message.content} - {error}")
            embed = discord.Embed(description="**An error has occurred, contact Arbin.**", color=FAIL_COLOR)
            # await messagesend(ctx, embed, allowgeneral=True, reject=False)
    except:
        log.exception("command error: ")
'''


@bot.command(name="last", aliases=["lastraid", "lastraids", "raids"])
@commands.check(logcommand)
async def lastraids(ctx, *args):
    embed = discord.Embed(description="**Please wait, fetching information...**", color=INFO_COLOR)
    respo = await messagesend(ctx, embed, allowgeneral=True, reject=False)
    enclist = await wclbot.guild(guild, server, region)
    a = 1
    nzone = 0
    tt = 0
    if args:
        if args[0].lower() == "mc":
            nzone = 1000
            tt = RZONE[nzone]
        elif args[0].lower() == "zg":
            nzone = 1003
            tt = RZONE[nzone]
        elif args[0].lower() == "ony" or args[0].lower() == "onyxia":
            nzone = 1001
            tt = RZONE[nzone]
        elif args[0].lower() == "bwl":
            nzone = 1002
            tt = RZONE[nzone]
        elif args[0].lower() == "aq20":
            nzone = 1004
            tt = RZONE[nzone]
        elif args[0].lower() == "aq40":
            nzone = 1005
            tt = RZONE[nzone]
        elif args[0].lower() == "aq":
            if args[1] == "20":
                nzone = 1004
                tt = RZONE[nzone]
            if args[1] == "40":
                nzone = 1005
                tt = RZONE[nzone]
        else:
            await respo.delete()
            await ctx.send(f"Invalid instance {args[0]}")
    if tt == 0:
        tttitle = f"Last 5 Logged Raids for {guild}"
    else:
        tttitle = f"Last 5 Logged {tt} Raids for {guild}"
    embed = discord.Embed(title=tttitle, color=INFO_COLOR)
    for each in enclist:
        if (each['zone'] == nzone or nzone == 0) and (a <= 5):
            kills, wipes, size, lastboss = await fight_data(each['id'])
            embed.add_field(name=f"{RZONE[each['zone']]} - {convert_time(each['start'], dateonly=True)} ({each['title']})", value=f"{convert_time (each['start'], timeonly=True)}-{convert_time(each['end'], timeonly=True)} - {elapsedTime(epochtz(each['start']), epochtz(each['end']))}\n[Bosses Killed: ({kills}\{BZONE[each['zone']]}) with {wipes} Wipes - Last Boss: {lastboss}](https://classic.warcraftlogs.com/reports/{each['id']})", inline=False)
            a = a + 1
    if a == 1:
        embed = discord.Embed(description=f"No raids were found for {guild.title()} on {server.capitalize()}", color=FAIL_COLOR)
    await respo.delete()
    await messagesend(ctx, embed, allowgeneral=True, reject=False)


@bot.command(name="news", aliases=["wownews", "warcraftnews"])
@commands.check(logcommand)
async def news(ctx, *args):
    embed = discord.Embed(description="Please wait, fetching information...", color=INFO_COLOR)
    respo = await messagesend(ctx, embed, allowgeneral=True, reject=False)
    news = await tsmbot.news()
    embed = discord.Embed(title=f'World of Warcraft Classic News', color=INFO_COLOR)
    for each in news:
        embed.add_field(name=f"**{each['title']}**", value=f"{fix_news_time(each['pubDate'])}\n[{each['content']}]({each['link']})", inline=False)
    await respo.delete()
    await messagesend(ctx, embed, allowgeneral=True, reject=False)


@bot.command(name="info", aliases=["player", "playerinfo"])
@commands.check(logcommand)
async def info(ctx, *args):
    if args:
        embed = discord.Embed(description="Please wait, fetching information...", color=INFO_COLOR)
        respo = await messagesend(ctx, embed, allowgeneral=True, reject=False)
        player = Player(args[0])
        await player.fetch()
        if player.exists:
            embed = discord.Embed(title=f'{args[0].capitalize()} on {region}-{server}', color=INFO_COLOR)
            # embed.set_author(name=args[0].capitalize())
            embed.add_field(name=f"Class:", value=f"{player.playerclass}")
            embed.add_field(name=f"Spec:", value=f"{player.playerspec}")
            embed.add_field(name=f"Role:", value=f"{player.playerrole}")
            # embed.add_field(name=f"Gear Enchants:", value=f"{}")
            # embed.add_field(name=f"Avg Item Level for fight:", value=f"{")
            # embed.add_field(name=f"Last Fight Percentile:", value=f"{truncate_float(perc, 1)}%")
            # embed.add_field(name=f"Last Fight Rank:", value="{:,} of {:,}".format(rank, outof))
            embed.add_field(name=f"Encounters Logged:", value=f"{player.totalencounters}")
            embed.add_field(name=f"MC Bosses Logged:", value=f"{player.mccount}")
            embed.add_field(name=f"Ony Raids Logged:", value=f"{player.onycount}")
            embed.add_field(name=f"BWL Bosses Logged:", value=f"{player.bwlcount}")
            embed.add_field(name=f"ZG Bosses Logged:", value=f"{player.zgcount}")
            embed.add_field(name=f"AQ20 Bosses Logged:", value=f"{player.aq20count}")
            embed.add_field(name=f"AQ40 Bosses Logged:", value=f"{player.aq40count}")
            elen = len(player.lastencounters) - 1
            msg = ""
            while elen >= 0:
                msg = msg + f"{convert_time(player.lastencounters[elen][1]['startTime'], dateonly=True)}  [{RZONE[BOSSREF[player.lastencounters[elen][1]['encounterName']]]}](https://classic.warcraftlogs.com/reports/{player.lastencounters[elen][1]['reportID']}) Last Boss: {player.lastencounters[elen][1]['encounterName']}\n"
                elen = elen - 1
            embed.add_field(name="Last 5 Raids Logged:", value=msg, inline=False)
            await respo.delete()
            await messagesend(ctx, embed, allowgeneral=True, reject=False)
        else:
            msg = "Cannot find character {} in warcraft logs".format(player.playername)
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await respo.delete()
            await messagesend(ctx, embed, allowgeneral=True, reject=False)
    else:
        msg = f"You must specify a game character to get info for"
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(ctx, embed, allowgeneral=True, reject=False)


@bot.command(name="gear", aliases=["playergear"])
@commands.check(logcommand)
async def gear(ctx, *args):
    if args:
        embed = discord.Embed(description="Please wait, fetching information...", color=INFO_COLOR)
        respo = await messagesend(ctx, embed, allowgeneral=True, reject=False)
        player = Player(args[0])
        await player.fetch()
        # Addfail check like items #####################
        if player.exists:
            embed = discord.Embed(title=f"{args[0].capitalize()}'s gear from {player.geardate}", color=INFO_COLOR)
            for item in player.gearlist:
                if 'name' in item and item['slot'] != 3:
                    if 'itemLevel' in item:
                        il = f"({item['itemLevel']})"
                    else:
                        il = ""
                    if 'permanentEnchantName' in item:
                        en = f"{item['permanentEnchantName']}"
                    else:
                        en = ""
                    if 'id' in item:
                        iid = item['id']
                    else:
                        iid = ""
                    embed.add_field(name=f"{GEAR_ORDER[item['slot']]}:", value=f"**[{item['name']}](https://classic.wowhead.com/item={iid}) {il}**\n{en}", inline=True)
            await respo.delete()
            await messagesend(ctx, embed, allowgeneral=True, reject=False)
        else:
            msg = "Cannot find character {} in warcraft logs".format(player.playername)
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await respo.delete()
            await messagesend(ctx, embed, allowgeneral=True, reject=False)
    else:
        msg = f"You must specify a game character to list gear for"
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await respo.delete()
        await messagesend(ctx, embed, allowgeneral=False, reject=True)


@bot.command(name="item", aliases=["price", "itemprice"])
@commands.check(logcommand)
async def item(ctx, *args):
    if args:
        embed = discord.Embed(description="Please wait, fetching information...", color=INFO_COLOR)
        respo = await messagesend(ctx, embed, allowgeneral=True, reject=False)
        if not isinstance(args[0], Number):
            argstring = ' '.join(args)
            itemdata = await tsmbot.search(query=argstring, limit=1, threshold=search_threshold)
            if len(itemdata) != 0:
                itemid = itemdata[0]['itemId']
            else:
                msg = f"Cannot locate information for item: {argstring.title()}"
                embed = discord.Embed(description=msg, color=FAIL_COLOR)
                await respo.delete()
                await messagesend(ctx, embed, allowgeneral=False, reject=True)
                return None
        else:
            itemid = int(args[0])
        item = Item(itemid)
        ires = await item.fetch()
        if item.exists:
            if item.lastupdate is None:
                dsg = 'Prices not available for this item'
            else:
                dsg = f'Prices from {faction.capitalize()} on {server.capitalize()} at {fix_item_time(item.lastupdate)}'
            embed = discord.Embed(title="", description=dsg, color=INFO_COLOR)
            embed.set_author(name=item.name, url=f"https://classic.wowhead.com/item={item.id}", icon_url=item.icon)
            msg = ""
            for tag in item.tags:
                msg = msg + f"{tag}\n"
            if msg == "":
                msg = "None"
            embed.add_field(name=f"Tags:", value=msg)
            embed.add_field(name=f"Item Level:", value=f"{item.level} ")
            embed.add_field(name=f"Required Level:", value=f"{item.requiredlevel} ")
            embed.add_field(name=f"Sell Price:", value=f"{convertprice(item.sellprice)} ")
            embed.add_field(name=f"Vendor Price:", value=f"{convertprice(item.vendorprice)} ")
            if isinstance(item.current_auctions, Number):
                ica = f'**{item.current_auctions:,d}**'
            else:
                ica = f'Not Available'
            if isinstance(item.current_quantity, Number):
                icb = f'**{item.current_quantity:,d}**'
            else:
                icb = f'Not Available'
            embed.add_field(name=f"Current Auctions/Prices:", value=f"Auctions: **{ica}**\nQuantity Available: **{icb}**\nMarket Value: **{convertprice(item.current_marketvalue)}**\nHistorical Value: **{convertprice(item.current_historicalvalue)}**\nMinimum Buyout: **{convertprice(item.current_minbuyout)}**", inline=False)
            if isinstance(item.previous_auctions, Number):
                ica = f'**{item.previous_auctions:,d}**'
            else:
                ica = f'Not Available'
            if isinstance(item.previous_quantity, Number):
                icb = f'**{item.previous_quantity:,d}**'
            else:
                icb = f'Not Available'
            embed.add_field(name=f"Previous Auctions/Prices:", value=f"Auctions: **{ica}**\nQuantity Available: **{icb}**\nMarket Value: **{convertprice(item.previous_marketvalue)}**\nHistorical Value: **{convertprice(item.previous_historicalvalue)}**\nMinimum Buyout: **{convertprice(item.previous_minbuyout)}**", inline=False)
            msg = ""
            for val in filter_details(item.name, item.tags, item.tooltip):
                msg = msg + f"{val}\n"
            if msg != "":
                embed.add_field(name=f"{item.name.title()} Details:", value=msg)
            await respo.delete()
            await messagesend(ctx, embed, allowgeneral=False, reject=True)
        else:
            if ires is None:
                msg = f"Cannot locate information for item: {item.name.title()}"
                embed = discord.Embed(description=msg, color=FAIL_COLOR)
                await respo.delete()
                await messagesend(ctx, embed, allowgeneral=False, reject=True)
            elif not ires:
                msg = f"Error retreiving information, please try again later."
                embed = discord.Embed(description=msg, color=FAIL_COLOR)
                await respo.delete()
                await messagesend(ctx, embed, allowgeneral=False, reject=True)
    else:
        msg = f"You must specify a item name or item id to get prices for"
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await respo.delete()
        await messagesend(ctx, embed, allowgeneral=False, reject=True)


@bot.command(name="setting", aliases=["set", "settings"])
@commands.check(logcommand)
async def setting(ctx, *args):
    if args:
        # Add settings logic ############
        # configdata.set('bug_tracker', 'password', 'secret')
        if not path.exists(configfile) or stat(configfile).st_size == 0:
            with open(configfile, 'w') as cf:
                configdata.write(cf)
            log.info(f'New config written to file: {configfile}')
        else:
            log.error(f"Error writing config to: {configfile} File doesn't exist or is empty")
            # Add embed response to config save error ############
    else:
        pass  # Add response to missing args  ############
    msg = "Commands can be privately messaged directly to the bot or in channels"
    embed = discord.Embed(title="WoW Info Classic Bot Commands:", description=msg, color=HELP_COLOR)
    embed.add_field(name=f"**`{command_prefix}raids [optional instance name]`**", value=f"Last 5 raids for the guild, [MC,ONY,BWL,ZG,AQ20,AQ40]\nLeave instance name blank for all", inline=False)
    embed.add_field(name=f"**`{command_prefix}info <character name>`**", value=f"Character information from last logged encounters", inline=False)
    embed.add_field(name=f"**`{command_prefix}gear <character name>`**", value=f"Character gear from last logged encounters", inline=False)
    embed.add_field(name=f"**`{command_prefix}price <item name>`**", value=f"Price and information for an item", inline=False)
    embed.add_field(name=f"**`{command_prefix}item <item name>`**", value=f"Same as ?price", inline=False)
    embed.add_field(name=f"**`{command_prefix}news`**", value=f"Latest World of Warcraft Classic News", inline=False)
    await ctx.message.author.send(embed=embed)
    if (type(ctx.message.channel) != discord.channel.DMChannel and str(ctx.message.channel) != "bot-channel"):
        await ctx.message.delete()


@bot.command(name="admin", aliases=["root"], pass_context=True)
@commands.check(logcommand)
#@commands.check(is_admin)
async def admin(ctx, *args):
    #pprint(ctx.guild.id)
    #pprint(dir(ctx.message.author))
    pprint(await user_info(ctx))

'''
    if args:
        if args[0].startswith('con') or args[0] == 'servers':
            embed = discord.Embed(title="Servers Connected:", description=f"Discord Latency: {truncate_float(bot.latency, 2)}", color=HELP_COLOR)
            for eguild in bot.guilds:
                msg = f"ServerID: {eguild.id}\nShardID: {eguild.shard_id}\nChunked: {eguild.chunked}\nClients: {eguild.member_count}\n\n"
                embed.add_field(name=f"{eguild.name}", value=msg)
            async for each in bot.fetch_guilds():
                pprint(each)
            await ctx.message.author.send(embed=embed)
        if args[0] == 'invite':
            msg = 'https://discord.com/oauth2/authorize?bot_id=750867600250241086&scope=bot&permissions=604302400'
            embed = discord.Embed(description=msg, color=HELP_COLOR)
            await messagesend(ctx, embed, allowgeneral=False, reject=True)
    else:
        msg = f"You must specify an admin command"
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(ctx, embed, allowgeneral=False, reject=True)
'''

@bot.command(name="help", aliases=["helpme", "commands"])
@commands.check(logcommand)
async def help(ctx):
    msg = "Commands can be privately messaged directly to the bot or in channels"
    embed = discord.Embed(title="WoW Info Classic Bot Commands:", description=msg, color=HELP_COLOR)
    embed.add_field(name=f"**`{command_prefix}raids [optional instance name]`**", value=f"Last 5 raids for the guild, [MC,ONY,BWL,ZG,AQ20,AQ40]\nLeave instance name blank for all", inline=False)
    embed.add_field(name=f"**`{command_prefix}info <character name>`**", value=f"Character information from last logged encounters", inline=False)
    embed.add_field(name=f"**`{command_prefix}gear <character name>`**", value=f"Character gear from last logged encounters", inline=False)
    embed.add_field(name=f"**`{command_prefix}price <item name>`**", value=f"Price and information for an item", inline=False)
    embed.add_field(name=f"**`{command_prefix}item <item name>`**", value=f"Same as ?price", inline=False)
    embed.add_field(name=f"**`{command_prefix}news`**", value=f"Latest World of Warcraft Classic News", inline=False)
    await ctx.message.author.send(embed=embed)
    if (type(ctx.message.channel) != discord.channel.DMChannel and str(ctx.message.channel) != "bot-channel"):
        await ctx.message.delete()


def main():
    bot.run(discordkey)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.info(f'Termination signal [KeyboardInterrupt] Closing web sessions.')
        wclbot.close()
        tsmbot.close()
        log.info(f'Exiting.')
        exit(0)
        try:
            exit(0)
        except SystemExit:
            _exit(0)
    except:
        log.critical(f'Main Exception Caught!')
