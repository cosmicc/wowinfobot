#!/usr/bin/env python3.8
import signal
from configparser import ConfigParser
from datetime import datetime
from math import trunc
from numbers import Number
from os import _exit, path, stat
from pathlib import Path
from sys import argv, exit, stdout

import discord
from discord.ext import commands
from loguru import logger as log
from prettyprinter import pprint
from pytz import timezone

from apifetch import BlizzardAPI, NexusAPI, WarcraftLogsAPI
from guildconfigparser import GuildConfigParser, RedisPool
from processlock import PLock

configfile = '/etc/wowinfobot.cfg'
signals = (0, 'SIGHUP', 'SIGINT', 'SIGQUIT', 4, 5, 6, 7, 8, 'SIGKILL', 10, 11, 12, 13, 14, 'SIGTERM')


def signal_handler(signal, frame):
    log.warning(f'Termination signal [{signals[signal]}] caught. Closing web sessions...')
    tsmclient.close()
    log.info(f'Exiting.')
    exit(0)


signal.signal(signal.SIGTERM, signal_handler)  # Graceful Shutdown
signal.signal(signal.SIGHUP, signal_handler)  # Reload/Restart
signal.signal(signal.SIGINT, signal_handler)  # Hard Exit
signal.signal(signal.SIGQUIT, signal_handler)  # Hard Exit

head_dir = Path(".") / ".git" / "HEAD"
with head_dir.open("r") as f:
    content = f.read().splitlines()
for line in content:
    if line[0:4] == "ref:":
        BRANCH = line.partition("refs/heads/")[2]

if BRANCH != 'develop':
    processlock = PLock()
    processlock.lock()

if not path.exists(configfile) or stat(configfile).st_size == 0:
    log.error(f"Config file: {configfile} doesn't exist or is empty. Exiting.")
    exit(1)

systemconfig = ConfigParser()
systemconfig.read(configfile)

configtemplate = {'general': ['loglevel', 'logfile'], 'discord': ['api_key'], 'warcraftlogs_api': ['api_url'], 'blizzard_api': ['api_url'], 'tsm_api': ['api_url']}

for section, options in configtemplate.items():
    if not systemconfig.has_section(section):
        log.error(f'Error: Missing configuration section {section} in config file: {configfile}. Exiting.')
        exit(1)
    else:
        for option in options:
            if not systemconfig.has_option(section, option):
                log.error(f'Error: Missing config option {option} in {section} in config file: {configfile}. Exiting.')
                exit(1)

logfile = Path(systemconfig.get("general", "logfile"))
redis_host = systemconfig.get("general", "redis_host")
redis_port = systemconfig.get("general", "redis_port")
redis_db = systemconfig.get("general", "redis_db")
discordkey = systemconfig.get("discord", "api_key")
discordkey_dev = systemconfig.get("discord", "dev_key")
superadmin_id = systemconfig.get("discord", "superadmin_id")
bliz_int_client = systemconfig.get("blizzard_api", "client_id")
bliz_int_secret = systemconfig.get("blizzard_api", "secret")
wcl_url = systemconfig.get("warcraftlogs_api", "api_url")
tsm_url = systemconfig.get("tsm_api", "api_url")

consoleformat = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>| <level>{level: <8}</level> | <level>{message}</level> |<cyan>{function}</cyan>:<cyan>{line}</cyan>"
logformat = "{time:YYYY-MM-DD HH:mm:ss.SSS}| {level: <8} | {message} |{function}:{line}"

log.remove()

if len(argv) > 1 or BRANCH == "develop":
    ll = "DEBUG"
    log.add(sink=stdout, level=ll, format=consoleformat, colorize=True)
    if BRANCH == "develop":
        devfile = logfile.stem + "-dev" + logfile.suffix
        logfile = logfile.parent / devfile
else:
    ll = "INFO"

log.add(sink=str(logfile), level=ll, buffering=1, enqueue=True, backtrace=True, format=logformat, diagnose=True, serialize=False, delay=False, colorize=False, rotation="5 MB", retention="1 month", compression="tar.gz")

log.debug(f'System configuration loaded successfully from {configfile}')
log.debug(f'Logfile started: {logfile}')

if BRANCH == 'develop':
    log.warning(f'WoWInfoClassic Bot is starting in DEV MODE!')
else:
    log.info(f'WoWInfoClassic Bot is starting in PRODUCTION MODE!')

bot = commands.Bot(command_prefix="=", case_insensitive=True)
bot.remove_command("help")
log.debug('Discord class initalized')

redis = RedisPool(redis_host, redis_port, redis_db)
bot.loop.create_task(redis.connect())
tsmclient = NexusAPI(tsm_url)
log.debug('NexusAPI class initalized')

SUCCESS_COLOR = 0x00FF00
FAIL_COLOR = 0xFF0000
INFO_COLOR = 0x0088FF
HELP_COLOR = 0xFF8800

COMMAND_PREFIXES = {1: ["?", "Question Mark"], 2: [".", "Period"], 3: ["!", "Exclimation Point"], 4: ["#", "Pound"], 5: ["\\", "Backslash"], 6: ["%", "Percent"], 7: ["-", "Minus"], 8: ["$", "Dollar Sign"], 9: ["&", "Ampersand"], 10: ["*", "Asterisk"], 11: ["^", "Carat"], 12: [">", "Greater Than"]}

GEAR_ORDER = {0: 'Head', 1: 'Neck', 2: 'Shoulders', 3: 'Shirt', 4: 'Chest', 5: 'Belt', 6: 'Legs', 7: 'Boots', 8: 'Bracers', 9: 'Hands', 10: 'Ring', 11: 'Ring', 12: 'Trinket', 13: 'Trinket', 14: 'Back', 15: 'Main Hand', 16: 'Off-Hand', 17: 'Ranged', 18: 'Tabard'}

item_quality = {1: 'Common', 2: 'Uncommon', 3: 'Rare', 4: 'Epic', 5: 'Legendary', 6: 'Artifact'}

ROLES = ['Tank', 'Healer', 'DPS']

RZONE = {1005: "Ahn'Qiraj 40", 1002: "Blackwing Lair", 1004: "Ahn'Qiraj 20", 1000: "Molten Core", 1003: "Zul'Gurub", 1001: "Onyxia"}

BOSSREF = {'Onyxia': 1001, 'Ragnaros': 1000, 'Lucifron': 1000, 'Magmadar': 1000, 'Gehennas': 1000, 'Garr': 1000, 'Baron Geddon': 1000, 'Shazzrah': 1000, 'Sulfuron Harbinger': 1000, 'Golemagg the Incinerator': 1000, 'Majordomo Executus': 1000, 'Ossirian the Unscarred': 1004, 'Ayamiss the Hunter': 1004, 'Buru the Gorger': 1004, 'Moam': 1004, 'General Rajaxx': 1004, 'Kurinnaxx': 1004, 'Nefarian': 1002, 'Chromaggus': 1000, "Jin'do the Hexxer": 1003, 'High Priest Thekal': 1003, "C'Thun": 1005, 'Ouro': 1005, 'Hakkar': 1003, 'Flamegor': 1002, 'Ebonroc': 1002, 'Princess Huhuran': 1005, 'The Prophet Skeram': 1005, 'Firemaw': 1002, 'Broodlord Lashlayer': 1002, 'Vaelastrasz the Corrupt': 1002, 'Viscidus': 1005, 'Twin Emperors': 1005}

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

running_setup = {}


def apply_timezone(date_obj, tz):
    date_obj = timezone('UTC').localize(date_obj)
    return date_obj.astimezone(timezone(tz))


def _epoch_to_dto(epoch):
    fixedepoch = int(str(epoch)[:10])
    return datetime.fromtimestamp(fixedepoch)


def convert_time(dtime, timeonly=False, dateonly=False, tz=None):
    if isinstance(dtime, str) or isinstance(dtime, int):
        date_obj = _epoch_to_dto(dtime)
    else:
        date_obj = dtime
    if tz is not None:
        date_obj = apply_timezone(date_obj, tz)
    if timeonly:
        return date_obj.strftime('%-I:%M%p')
    elif dateonly:
        return date_obj.strftime('%m/%d/%y')
    else:
        return date_obj.strftime('%m/%d/%y %-I:%M%p')


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
    start_time = int(str(start_time)[:10])
    stop_time = int(str(stop_time)[:10])
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


async def user_info(message):
    if type(message.channel) == discord.channel.DMChannel:
        for guild in bot.guilds:
            member = discord.utils.get(guild.members, id=message.author.id)
            if member:
                is_admin_role = False
                is_user_role = False
                guildconfig = GuildConfigParser(redis, guild.id)
                await guildconfig.read()
                admin_id = guildconfig.get("discord", "admin_role_id")
                user_id = guildconfig.get("discord", "user_role_id")
                for role in member.roles:
                    if str(role.id) == str(admin_id):
                        is_admin_role = True
                    if str(role.id) == str(user_id):
                        is_user_role = True
                if str(message.author.id) == str(superadmin_id):
                    is_superadmin = True
                else:
                    is_superadmin = False
                return {'user_id': message.author.id, 'user_name': message.author.name, 'guild_id': guild.id, 'guild_name': guild.name, 'channel': 'DMChannel', 'is_member': True, 'is_user': is_user_role, 'is_admin': is_admin_role, 'is_superadmin': is_superadmin}
            else:
                return {'user_id': message.author.id, 'user_name': message.author.name, 'guild_id': None, 'guild_name': None, 'channel': 'DMChannel', 'is_member': False, 'is_user': False, 'is_admin': False, 'is_superadmin': is_superadmin}
    else:
        is_admin_role = False
        is_user_role = False
        guildconfig = GuildConfigParser(redis, message.author.guild.id)
        await guildconfig.read()
        admin_id = guildconfig.get("discord", "admin_role_id")
        user_id = guildconfig.get("discord", "user_role_id")
        member = discord.utils.get(message.author.guild.members, id=message.author.id)
        for role in member.roles:
            if str(role.id) == str(admin_id):
                is_admin_role = True
            if str(role.id) == str(user_id):
                is_user_role = True
            if str(message.author.id) == str(superadmin_id):
                is_superadmin = True
            else:
                is_superadmin = False
        return {'user_id': message.author.id, 'user_name': message.author.name, 'guild_id': message.author.guild.id, 'guild_name': message.author.guild.name, 'channel': message.channel.id, 'is_member': True, 'is_user': is_user_role, 'is_admin': is_admin_role, 'is_superadmin': is_superadmin}


def filter_details(name, tags, labels):
    details = []
    for line in labels:
        label = line['label']
        if label != 'Sell Price:' and not label.startswith('Item Level') and not label.startswith('Requires Level') and label not in tags and label != name:
            details.append(label)
    return details


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

    async def fetch(self):
        itemdata = await tsmclient.price(self.id, self.server.lower(), self.faction.lower())
        if 'error' in itemdata:
            return itemdata
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

    def __init__(self, gconfig, aclient, playername):
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
        self.client = aclient
        self.guildconfig = gconfig
        self.timezone = gconfig.get("server", "server_timezone")

    async def fetch(self):
        for kkey, vval in RZONE.items():
            parselist = await self.client.parses(self.playername, self.guildconfig.get("server", "server_name").title(), self.guildconfig.get("server", "server_region").upper(), zone=kkey)
            if await checkhttperrors(None, None, None, None, parselist):
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
                    reporttable = await self.client.tables('casts', encounter[1]['reportID'], start=0, end=18000)

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
                                        self.geardate = convert_time(encounter[1]['startTime'], self.timezone, dateonly=True)
                                    elif len(self.gearlist) < 1:
                                        self.gearlist = entry['gear']
                                        self.geardate = convert_time(encounter[1]['startTime'], self.timezone, dateonly=True)
            self.lastencounter = self.lastencounters[len(self.lastencounters) - 1][1]
        return parselist


@bot.event
async def on_ready():
        log.log("SUCCESS", f"Discord logged in as {bot.user.name} id {bot.user.id}")
        activity = discord.Game(name="Msg Me!")
        try:
            await bot.change_presence(status=discord.Status.online, activity=activity)
        except:
            log.error("Exiting")


async def fight_data(wclclient, fid):
    fight = await wclclient.fights(fid)
    kills = 0
    wipes = 0
    size = 0
    for key, value in fight.items():
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


def logcommand(message, user):
    if type(message.channel) == discord.channel.DMChannel:
        dchan = "Direct Message"
    else:
        dchan = message.channel
    log.log("INFO", f"Request [{message.content}] from [{message.author}] in [#{dchan}] from [{user['guild_name']}]")


async def wait_message(message, user, guildconfig):
    await message.channel.trigger_typing()
    return None


def error_embed(message):
    return discord.Embed(description="Resource unavailable, please try again later.", color=FAIL_COLOR)


async def messagesend(message, embed, user, guildconfig, respo=None):
    try:
        if respo is not None:
            await respo.delete()
        if type(message.channel) == discord.channel.DMChannel:
            return await message.author.send(embed=embed)
        elif guildconfig.get('discord', 'pm_only') == "True" or (guildconfig.get('discord', 'limit_to_channel') != "Any" and str(message.channel.id) != guildconfig.get('discord', 'limit_to_channel_id')):
            await message.delete()
            return await message.author.send(embed=embed)
        else:
            return await message.channel.send(embed=embed)
    except:
        log.exception("Critical error in message send")


async def checkhttperrors(message, user, guildconfig, respo, checkdata):
    if isinstance(checkdata, dict):
        newcheck = checkdata
    elif isinstance(checkdata, list):
        if len(checkdata) > 0:
            newcheck = checkdata[0]
        else:
            return True
    else:
        if message is not None:
            log.error(f'Wrong type to check in checkhttperrors type: {type(checkdata)}')
            embed = discord.Embed(description="Resource unavailable, please try again later.", color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig, respo=respo)
        return False
    if 'error' in newcheck:
        if newcheck['error'] == 401:
            embed = discord.Embed(description="API key invalid. Check settings.", color=FAIL_COLOR)
        else:
            embed = discord.Embed(description="Resource unavailable, please try again later.", color=FAIL_COLOR)
        if message is not None:
            await messagesend(message, embed, user, guildconfig, respo=respo)
        return False
    else:
        return True


@bot.event
async def on_message(message):
    if message.author.id != bot.user.id:
        user = await user_info(message)
        if user['guild_id'] is None:
            pass
        else:
            guildconfig = GuildConfigParser(redis, user['guild_id'])
            await guildconfig.read()
            if user['user_id'] in running_setup:
                if message.content.lower() == 'cancel':
                    title = 'Setup wizard has been cancelled'
                    msg = f'Type {guildconfig.get("discord", "command_prefix")}setup in the future to run the setup wizard again'
                    embed = discord.Embed(title=title, description=msg, color=FAIL_COLOR)
                    del running_setup[user['user_id']]
                    await messagesend(message, embed, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 1:
                    await response1(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 2:
                    await response2(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 3:
                    await response3(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 4:
                    await response4(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 5:
                    await response5(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 6:
                    await response6(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 7:
                    await response7(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 8:
                    await response8(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 9:
                    await response9(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 10:
                    await response10(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 11:
                    await response11(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 12:
                    await response12(message, user, guildconfig)
                elif running_setup[user['user_id']]['setupstep'] == 13:
                    await response13(message, user, guildconfig)
            elif guildconfig.get("discord", "setupran") == "False" and type(message.channel) == discord.channel.DMChannel and message.content == "setup":
                await setup(message, user, guildconfig)
            elif guildconfig.get("discord", "setupran") == "False" and type(message.channel) == discord.channel.DMChannel:
                    title = 'Bot has not been setup!'
                    msg = f'Type "setup" to run the setup wizard.'
                    embed = discord.Embed(title=title, description=msg, color=FAIL_COLOR)
                    await messagesend(message, embed, user, guildconfig)
            else:
                if message.content.startswith(guildconfig.get('discord', 'command_prefix')):
                    if user['is_user'] or user['is_admin']:
                        args = message.content[1:].split(' ')
                        if args[0].lower() in ['raids', 'last', 'lastraids', 'lastraid']:
                            args.pop(0)
                            await lastraids(message, user, guildconfig, *args)
                        elif args[0].lower() in ["news", "wownews", "warcraftnews"]:
                            args.pop(0)
                            await news(message, user, guildconfig, *args)
                        elif args[0].lower() in ["help", "commands", "helpme"]:
                            args.pop(0)
                            await help(message, user, guildconfig, *args)
                        elif args[0].lower() == "settings" and type(message.channel) == discord.channel.DMChannel and user['is_admin']:
                            args.pop(0)
                            await setting(message, user, guildconfig, *args)
                        elif args[0].lower() in ["player", "playerinfo", "pinfo"]:
                            args.pop(0)
                            await playerinfo(message, user, guildconfig, *args)
                        elif args[0].lower() in ["gear", "playergear", "playeritems"]:
                            args.pop(0)
                            await playergear(message, user, guildconfig, *args)
                        elif args[0].lower() in ["item", "price", "itemprice", "iteminfo"]:
                            args.pop(0)
                            await item(message, user, guildconfig, *args)
                        elif args[0].lower() in ["server", "status", "serverstatus"]:
                            args.pop(0)
                            await status(message, user, guildconfig, *args)
                        elif args[0].lower() in ["admin"] and type(message.channel) == discord.channel.DMChannel and user['is_superadmin']:
                            args.pop(0)
                            await admin(message, user, guildconfig, *args)
                        elif args[0].lower() in ["setup"] and type(message.channel) == discord.channel.DMChannel and user['is_admin']:
                            args.pop(0)
                            await setup(message, user, guildconfig, *args)
                        elif args[0].lower() in ["test"] and user['is_admin']:
                            args.pop(0)
                            await test(message, user, guildconfig, *args)
                else:
                    if type(message.channel) == discord.channel.DMChannel:
                        await help(message, user, guildconfig)


async def status(message, user, guildconfig, *args):
    logcommand(message, user)
    respo = await wait_message(message, user, guildconfig)
    try:
        blizcli = BlizzardAPI(guildconfig.get("blizzard", "client_id"), guildconfig.get("blizzard", "client_secret"), guildconfig.get("server", "server_region"))
        await blizcli.authorize()
        serverstatus = await blizcli.realm_status(guildconfig.get("server", "server_id"))
        await blizcli.close()
        if await checkhttperrors(message, user, guildconfig, respo, serverstatus):
            embed = discord.Embed(title=f'{guildconfig.get("server", "server_name").title()} Server Status', color=INFO_COLOR)
            embed.add_field(name='Status', value=serverstatus["status"]["name"]["en_US"])
            if serverstatus["has_queue"]:
                hasqueue = "Yes"
            else:
                hasqueue = "No"
            embed.add_field(name='Queue', value=hasqueue)
            embed.add_field(name='Population', value=serverstatus["population"]["name"]["en_US"])
            embed.add_field(name='Type', value=guildconfig.get('server', 'server_type'))
            embed.add_field(name='Category', value=guildconfig.get('server', 'server_category'))
            embed.add_field(name='Region', value=guildconfig.get('server', 'server_region_name'), inline=False)
            embed.add_field(name='Timezone', value=guildconfig.get('server', 'server_timezone'), inline=False)
            await messagesend(message, embed, user, guildconfig, respo=respo)
    except:
        log.exception('Exception in status function')
        await messagesend(message, error_embed(message), user, guildconfig, respo=respo)


async def lastraids(message, user, guildconfig, *args):
    logcommand(message, user)
    respo = await wait_message(message, user, guildconfig)
    try:
        wclclient = WarcraftLogsAPI(wcl_url, guildconfig.get('warcraftlogs', 'api_key'))
        tz = guildconfig.get('server', 'server_timezone')
        enclist = await wclclient.guild(user['guild_name'], guildconfig.get('server', 'server_name'), guildconfig.get('server', 'server_region'))
        if await checkhttperrors(message, user, guildconfig, respo, enclist):
            a = 1
            nzone = 0
            tt = 0
            cont = True
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
                    embed = discord.Embed(description=f"Invalid instance {args[0]}", color=FAIL_COLOR)
                    await wclclient.close()
                    await messagesend(message, embed, user, guildconfig, respo=respo)
                    cont = False
            if cont:
                if tt == 0:
                    tttitle = f"Last 5 Logged Raids for {user['guild_name']}"
                else:
                    tttitle = f"Last 5 Logged {tt} Raids for {user['guild_name']}"
                embed = discord.Embed(title=tttitle, color=INFO_COLOR)
                for each in enclist:
                    if (each['zone'] == nzone or nzone == 0) and (a <= 5):
                        kills, wipes, size, lastboss = await fight_data(wclclient, each['id'])
                        rtstart = convert_time(each['start'], timeonly=True, tz=tz)
                        rtstop = convert_time(each['end'], timeonly=True, tz=tz)
                        embed.add_field(name=f"{RZONE[each['zone']]} - {convert_time(each['start'], dateonly=True, tz=tz)} ({each['title']})", value=f"{rtstart}-{rtstop} - {elapsedTime(each['start'], each['end'])}\n[Bosses Killed: ({kills}\{BZONE[each['zone']]}) with {wipes} Wipes - Last Boss: {lastboss}](https://classic.warcraftlogs.com/reports/{each['id']})", inline=False)
                        a = a + 1
                if a == 1:
                    embed = discord.Embed(description=f"No raids were found for {guildconfig.get('server', 'guild_name').title()} on {[guildconfig.get('server', 'server_name').title()]}", color=FAIL_COLOR)
                await wclclient.close()
                await messagesend(message, embed, user, guildconfig, respo=respo)
    except:
        log.exception('Exception in lastraids function')
        await wclclient.close()
        await messagesend(message, error_embed(message), user, guildconfig, respo=respo)


async def news(message, user, guildconfig, *args):
    logcommand(message, user)
    respo = await wait_message(message, user, guildconfig)
    try:
        news = await tsmclient.news()
        if await checkhttperrors(message, user, guildconfig, respo, news):
            embed = discord.Embed(title=f'World of Warcraft Classic News', color=INFO_COLOR)
            for each in news:
                embed.add_field(name=f"**{each['title']}**", value=f"{fix_news_time(each['pubDate'], guildconfig.get('server','server_timezone'))}\n[{each['content']}]({each['link']})", inline=False)
            await respo.delete()
            await messagesend(message, embed, user, guildconfig)
    except:
        log.exception('Exception in news function')
        await messagesend(message, error_embed(message), user, guildconfig, respo=respo)


async def playerinfo(message, user, guildconfig, *args):
    logcommand(message, user)
    respo = await wait_message(message, user, guildconfig)
    try:
        if args:
            servertimezone = guildconfig.get('server', 'server_timezone')
            wclclient = WarcraftLogsAPI(wcl_url, guildconfig.get('warcraftlogs', 'api_key'))
            player = Player(guildconfig, wclclient, args[0])
            pp = await player.fetch()
            await wclclient.close()
            if await checkhttperrors(message, user, guildconfig, respo, pp):
                if player.exists:
                    embed = discord.Embed(title=f'{args[0].capitalize()} on {guildconfig.get("server", "server_region".upper())}-{guildconfig.get("server", "server_name").title()}', color=INFO_COLOR)
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
                        if player.lastencounters[elen][1] != 0:
                            msg = msg + f"{convert_time(player.lastencounters[elen][1]['startTime'], dateonly=True, tz=servertimezone)}  [{RZONE[BOSSREF[player.lastencounters[elen][1]['encounterName']]]}](https://classic.warcraftlogs.com/reports/{player.lastencounters[elen][1]['reportID']}) Last Boss: {player.lastencounters[elen][1]['encounterName']}\n"
                        elen = elen - 1
                    embed.add_field(name="Last 5 Raids Logged:", value=msg, inline=False)
                    await messagesend(message, embed, user, guildconfig, respo=respo)
                else:
                    msg = "Cannot find character {} in warcraft logs".format(player.playername)
                    embed = discord.Embed(description=msg, color=FAIL_COLOR)
                    await messagesend(message, embed, user, guildconfig, respo=respo)
        else:
            msg = f"You must specify a game character to get info for"
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig, respo=respo)
    except:
        log.exception(f'Exception in player info function')
        await messagesend(message, error_embed(message), user, guildconfig, respo=respo)


async def playergear(message, user, guildconfig, *args):
    logcommand(message, user)
    respo = await wait_message(message, user, guildconfig)
    playername = args[0]
    try:
        if args:
            wclclient = WarcraftLogsAPI(wcl_url, guildconfig.get('warcraftlogs', 'api_key'))
            player = Player(guildconfig, wclclient, playername)
            pp = await player.fetch()
            await wclclient.close()
            if await checkhttperrors(message, user, guildconfig, respo, pp):
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
                    await messagesend(message, embed, user, guildconfig, respo=respo)
                else:
                    msg = "Cannot find character {} in warcraft logs".format(player.playername)
                    embed = discord.Embed(description=msg, color=FAIL_COLOR)
                    await messagesend(message, embed, user, guildconfig, respo=respo)
        else:
            msg = f"You must specify a game character to list gear for"
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig, respo=respo)
    except:
        log.exception(f'Exception in player gear function')
        await messagesend(message, error_embed(message), user, guildconfig, respo=respo)


async def item(message, user, guildconfig, *args):
    logcommand(message, user)
    respo = await wait_message(message, user, guildconfig)
    try:
        if args:
            servertimezone = guildconfig.get("server", "server_timezone")
            if not isinstance(args[0], Number):
                argstring = ' '.join(args)
                itemdata = await tsmclient.search(query=argstring, limit=1, threshold='0.8')
                if await checkhttperrors(message, user, guildconfig, respo, itemdata):
                    if len(itemdata) != 0:
                        itemid = itemdata[0]['itemId']
                    else:
                        msg = f"Cannot locate information for item: {argstring.title()}"
                        embed = discord.Embed(description=msg, color=FAIL_COLOR)
                        await messagesend(message, embed, user, guildconfig, respo=respo)
                        return None
            else:
                itemid = int(args[0])
            item = Item(guildconfig.get("server", "server_name"), guildconfig.get("server", "faction"), itemid)
            ires = await item.fetch()
            if await checkhttperrors(message, user, guildconfig, respo, ires):
                if item.exists:
                    embed = discord.Embed(title="", description=f'[Wowhead Link](https://classic.wowhead.com/item={item.id}) / [ClassicDB Link](https://classicdb.ch/?item={item.id})', color=INFO_COLOR)
                    embed.set_author(name=item.name, url=f"https://classic.wowhead.com/item={item.id}", icon_url=item.icon)
                    msg = ""
                    for tag in item.tags:
                        msg = msg + f"{tag}\n"
                    if msg == "":
                        msg = "None"
                    embed.add_field(name=f"Tags:", value=msg)
                    embed.add_field(name=f"Item Level:", value=f"{item.level} ")
                    embed.add_field(name=f"Required Level:", value=f"{item.requiredlevel} ")
                    nprice = convertprice(item.sellprice)
                    if nprice == '0c':
                        embed.add_field(name=f"Vendor Price:", value="Not Sellable")
                    else:
                        embed.add_field(name=f"Vendor Price:", value=f"{convertprice(item.sellprice)} ")
                    # embed.add_field(name=f"Vendor Price:", value=f"{convertprice(item.vendorprice)} ")
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
                    if item.lastupdate is None:
                        dsg = 'Prices not available for this item'
                    else:
                        dsg = f'Prices from {guildconfig.get("server", "server_name").title()}-{guildconfig.get("server", "faction").capitalize()} on {fix_item_time(item.lastupdate, servertimezone)}'
                    embed.set_footer(text=dsg)
                    await messagesend(message, embed, user, guildconfig, respo=respo)
                else:
                    if ires is None:
                        msg = f"Cannot locate information for item: {item.name.title()}"
                        embed = discord.Embed(description=msg, color=FAIL_COLOR)
                        await messagesend(message, embed, user, guildconfig, respo=respo)
        else:
            msg = f"You must specify a item name or item id to get prices for"
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig, respo=respo)
    except:
        log.exception(f'Exception in item function')
        await messagesend(message, error_embed(message), user, guildconfig, respo=respo)


async def setup(message, user, guildconfig, *args):
    logcommand(message, user)
    if user['user_id'] not in running_setup:
        log.info(f"Starting Setup for {user['user_name']} from {user['guild_name']}")
        user['setupstep'] = 1
        running_setup[user['user_id']] = user
        if guildconfig.get("discord", "setupran") == "True":
            title = f'Setup has already been ran for server: {user["guild_name"]}\nWould you like to run it again?'
            msg = f'**1**: Yes\n**2**: No'
            embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
            await messagesend(message, embed, user, guildconfig)
        else:
            title = f"Welcome to the WowInfoClassic setup wizard for server: {user['guild_name']}"
            msg = "Type cancel at any time to cancel setup"
            embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
            await messagesend(message, embed, user, guildconfig)
            await setup2(message, user, guildconfig, *args)


async def response1(message, user, guildconfig, *args):
    resp = message.content
    if resp != '1' and resp != '2':
        log.warning(f"Invalid answer to start setup again [{message.content}]")
        msg = 'Invalid response.  Select 1 or 2'
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(message, embed, user, guildconfig)
        await setup(message, user, guildconfig, *args)
    elif resp == '1':
        await setup2(message, user, guildconfig, *args)
    elif resp == '2':
        title = f'Setup wizard has been cancelled for server: {user["guild_name"]}'
        msg = f'Type {guildconfig.get("discord", "command_prefix")}setup in the future to run the setup wizard again'
        embed = discord.Embed(title=title, description=msg, color=FAIL_COLOR)
        del running_setup[user['user_id']]
        await messagesend(message, embed, user, guildconfig)


async def setup2(message, user, guildconfig, *args):
    user['setupstep'] = 2
    running_setup[user['user_id']] = user
    title = 'Select your World of Warcraft Classic server region:'
    msg = '**1**: US\n**2**: EU'
    embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response2(message, user, guildconfig, *args):
    resp = message.content
    if resp != '1' and resp != '2':
        msg = 'Invalid selection. Please answer 1 or 2'
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(message, embed, user, guildconfig)
        await setup2(message, user, guildconfig, *args)
    else:
        if resp == '1':
            guildconfig.set('server', 'server_region', 'US')
        elif resp == '2':
            guildconfig.set('server', 'server_region', 'EU')
        await guildconfig.write()
        await setup3(message, user, guildconfig, *args)


async def setup3(message, user, guildconfig, *args):
    user['setupstep'] = 3
    running_setup[user['user_id']] = user
    title = 'Select your World of Warcraft Classic server:'
    blizcli = BlizzardAPI(bliz_int_client, bliz_int_secret, guildconfig.get("server", "server_region"))
    await blizcli.authorize()
    realms = await blizcli.realm_list()
    await blizcli.close()
    num = 1
    slist = {}
    for realm in realms['realms']:
        if not realm['name']['en_US'].startswith('US') and not realm['name']['en_US'].startswith('EU'):
            slist[num] = {'name': realm['name']['en_US'], 'slug': realm['slug'], 'id': realm['id']}
            num = num + 1
    msg = ''
    user['serverlist'] = sorted(slist.items())
    running_setup[user['user_id']] = user
    for sname, sval in sorted(slist.items()):
        msg = msg + f'**{sname}**: {sval["name"]}\n'
    embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response3(message, user, guildconfig, *args):
    resp = message.content
    try:
        int(resp)
    except:
        msg = 'Invalid server selection'
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(message, embed, user, guildconfig)
        await setup3(message, user, guildconfig, *args)
    else:
        setup_user = running_setup[user['user_id']]
        slist = setup_user['serverlist']
        if (int(resp) - 1) > len(slist) or (int(resp) - 1) < 1:
            msg = 'Invalid server selection'
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig)
            await setup3(message, user, guildconfig, *args)
        else:
            svr = slist[int(resp) - 1][1]
            blizcli = BlizzardAPI(bliz_int_client, bliz_int_secret, guildconfig.get("server", "server_region"))
            await blizcli.authorize()
            svr_info = await blizcli.realm_info(svr['slug'])
            await blizcli.close()
            guildconfig.set('server', 'server_name', svr_info['name']['en_US'])
            guildconfig.set('server', 'server_timezone', svr_info['timezone'])
            guildconfig.set('server', 'server_id', svr_info['id'])
            guildconfig.set('server', 'server_region_name', svr_info['region']['name']['en_US'])
            guildconfig.set('server', 'server_region_id', svr_info['region']['id'])
            guildconfig.set('server', 'server_locale', svr_info['locale'])
            guildconfig.set('server', 'server_type', svr_info['type']['type'])
            guildconfig.set('server', 'server_category', svr_info['category']['en_US'])
            guildconfig.set('server', 'server_slug', svr_info['slug'])
            await guildconfig.write()
            await setup4(message, user, guildconfig, *args)


async def setup4(message, user, guildconfig, *args):
    user['setupstep'] = 4
    running_setup[user['user_id']] = user
    title = 'Select your World of Warcraft Classic faction:'
    msg = '**1**: Alliance\n**2**: Horde'
    embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response4(message, user, guildconfig, *args):
    resp = message.content
    if resp != '1' and resp != '2':
        msg = 'Invalid selection.  Please answer 1 or 2'
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(message, embed, user, guildconfig)
        await setup2(message, user, guildconfig, *args)
    else:
        if resp == '1':
            guildconfig.set('server', 'faction', 'Alliance')
        elif resp == '2':
            guildconfig.set('server', 'faction', 'Horde')
        await guildconfig.write()
        await setup5(message, user, guildconfig, *args)


async def setup5(message, user, guildconfig, *args):
    user['setupstep'] = 5
    running_setup[user['user_id']] = user
    title = "Please enter your World of Warcraft Classic Guild's name:"
    embed = discord.Embed(title=title, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response5(message, user, guildconfig, *args):
    resp = message.content.title()
    guildconfig.set('server', 'guild_name', resp)
    await guildconfig.write()
    await setup6(message, user, guildconfig, *args)


async def setup6(message, user, guildconfig, *args):
    user['setupstep'] = 6
    running_setup[user['user_id']] = user
    msg = ''
    title = "Select which discord role is allowed to change bot settings (admin):"
    rguild = None
    for guild in bot.guilds:
        member = discord.utils.get(guild.members, id=message.author.id)
        if member:
            rguild = guild
            break
    num = 1
    roles = {}
    for role in rguild.roles:
        if role.name != '@everyone':
            roles[num] = role
            msg = msg + f'**{num}**: {role.name}\n'
            num = num + 1
    user['roles'] = roles
    running_setup[user['user_id']] = user
    embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response6(message, user, guildconfig, *args):
    resp = message.content
    try:
        int(resp)
    except:
        msg = 'Invalid role selection'
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(message, embed, user, guildconfig)
        await setup6(message, user, guildconfig, *args)
    else:
        if int(resp) > (len(running_setup[user['user_id']]['roles'])) or int(resp) < 1:
            msg = 'Invalid role selection'
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig)
            await setup6(message, user, guildconfig, *args)
        else:
            srole = running_setup[user['user_id']]['roles'][int(resp)]
            guildconfig.set('discord', 'admin_role_id', srole.id)
            guildconfig.set('discord', 'admin_role', srole.name)
            await guildconfig.write()
            await setup7(message, user, guildconfig, *args)


async def setup7(message, user, guildconfig, *args):
    user['setupstep'] = 7
    running_setup[user['user_id']] = user
    msg = ''
    title = "Select which discord role that should be allowed to use bot commands:"
    rguild = None
    for guild in bot.guilds:
        member = discord.utils.get(guild.members, id=message.author.id)
        if member:
            rguild = guild
            break
    num = 1
    roles = {}
    for role in rguild.roles:
        roles[num] = role
        msg = msg + f'**{num}**: {role.name}\n'
        num = num + 1
    user['roles'] = roles
    running_setup[user['user_id']] = user
    embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response7(message, user, guildconfig, *args):
    resp = message.content
    try:
        int(resp)
    except:
        msg = 'Invalid role selection'
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(message, embed, user, guildconfig)
        await setup7(message, user, guildconfig, *args)
    else:
        if int(resp) > (len(running_setup[user['user_id']]['roles'])) or int(resp) < 1:
            msg = 'Invalid role selection'
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig)
            await setup7(message, user, guildconfig, *args)
        else:
            srole = running_setup[user['user_id']]['roles'][int(resp)]
            guildconfig.set('discord', 'user_role_id', srole.id)
            guildconfig.set('discord', 'user_role', srole.name)
            await guildconfig.write()
            await setup8(message, user, guildconfig, *args)


async def setup8(message, user, guildconfig, *args):
    user['setupstep'] = 8
    running_setup[user['user_id']] = user
    title = 'Select where the bot should respond:'
    msg = '**1**: Private Message Only (No Channels)\n**2**: Private Message & 1 Specific Channel Only\n**3**: Private Message & Any Channel'
    embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response8(message, user, guildconfig, *args):
    resp = message.content
    if resp != '1' and resp != '2' and resp != '3':
        msg = 'Invalid selection.  Please answer 1, 2, or 3'
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(message, embed, user, guildconfig)
        await setup8(message, user, guildconfig, *args)
    else:
        if resp == '1':
            guildconfig.set('discord', 'pm_only', 'True')
            guildconfig.set('discord', 'limit_to_channel', 'None')
            await guildconfig.write()
            await setup10(message, user, guildconfig, *args)
        elif resp == '2':
            guildconfig.set('discord', 'pm_only', 'False')
            await guildconfig.write()
            await setup9(message, user, guildconfig, *args)
        elif resp == '3':
            guildconfig.set('discord', 'pm_only', 'False')
            guildconfig.set('discord', 'limit_to_channel', 'Any')
            await guildconfig.write()
            await setup10(message, user, guildconfig, *args)


async def setup9(message, user, guildconfig, *args):
    user['setupstep'] = 9
    running_setup[user['user_id']] = user
    msg = ''
    num = 1
    channels = {}
    title = 'Select which channel to limit the bot to:'
    for guild in bot.guilds:
        member = discord.utils.get(guild.members, id=message.author.id)
        if member:
            for channel in guild.text_channels:
                channels[num] = channel
                msg = msg + f'**{num}**: {channel}\n'
                num = num + 1
    user['channels'] = channels
    embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response9(message, user, guildconfig, *args):
    resp = message.content
    try:
        int(resp)
    except:
        msg = 'Invalid channel selection'
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(message, embed, user, guildconfig)
        await setup9(message, user, guildconfig, *args)
    else:
        if int(resp) > (len(running_setup[user['user_id']]['channels'])) or int(resp) < 1:
            msg = 'Invalid channel selection'
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig)
            await setup9(message, user, guildconfig, *args)
        else:
            chan = running_setup[user['user_id']]['channels'][int(resp)]
            guildconfig.set('discord', 'limit_to_channel_id', chan.id)
            guildconfig.set('discord', 'limit_to_channel', chan.name)
            await guildconfig.write()
            await setup10(message, user, guildconfig, *args)


async def setup10(message, user, guildconfig, *args):
    user['setupstep'] = 10
    running_setup[user['user_id']] = user
    title = 'Paste your Warcraft Logs API Key:'
    msg = ''
    if guildconfig.get("warcraftlogs", "api_key") != "None":
        msg = 'Type "keep" to keep your existing API key\n\n'
    msg = msg + 'If you do not have a Warcraft Logs API key, get one from here:\n[Warcraft Logs User Profile](https://classic.warcraftlogs.com/profile)\nBottom of the page under Web API, you must hava a valid free Warcraft Logs account.'
    embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response10(message, user, guildconfig, *args):
    if guildconfig.get("warcraftlogs", "api_key") != "None" and message.content.lower() == "keep":
        await setup11(message, user, guildconfig, *args)
    else:
        if len(message.content.lower()) != 32:
            msg = "That does not appear to be a valid API key"
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig)
            await setup10(message, user, guildconfig, *args)
        else:
            guildconfig.set('warcraftlogs', 'api_key', message.content)
            await guildconfig.write()
            await setup11(message, user, guildconfig, *args)


async def setup11(message, user, guildconfig, *args):
    user['setupstep'] = 11
    running_setup[user['user_id']] = user
    title = 'Paste your Blizzard API Client ID:'
    msg = ''
    if guildconfig.get("blizzard", "client_id") != "None":
        msg = 'Type "keep" to keep your existing client id\n\n'
    msg = msg + """If you do not have a Blizzard API client created, create one here:\n[Blizzard API Clients](https://develop.battle.net/access/clients)\nClick "Create Client", Then fill out the info (entries don't matter), to get a Blizzard Client ID & Secret"""
    embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response11(message, user, guildconfig, *args):
    if guildconfig.get("blizzard", "client_id") != "None" and message.content.lower() == "keep":
        await setup12(message, user, guildconfig, *args)
    else:
        if len(message.content.lower()) != 32:
            msg = "That does not appear to be a valid Client ID"
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig)
            await setup11(message, user, guildconfig, *args)
        else:
            guildconfig.set('blizzard', 'client_id', message.content)
            await guildconfig.write()
            await setup12(message, user, guildconfig, *args)


async def setup12(message, user, guildconfig, *args):
    user['setupstep'] = 12
    running_setup[user['user_id']] = user
    title = 'Paste your Blizzard API Client SECRET:'
    msg = ''
    if guildconfig.get("blizzard", "client_secret") != "None":
        msg = 'Type "keep" to keep your existing client secret\n\n'
    msg = msg + """From same Blizzard API client created above"""
    embed = discord.Embed(title=title, description=msg, color=HELP_COLOR)
    await messagesend(message, embed, user, guildconfig)


async def response12(message, user, guildconfig, *args):
    if guildconfig.get("blizzard", "client_secret") != "None" and message.content.lower() == "keep":
        await setup13(message, user, guildconfig, *args)
    else:
        if len(message.content.lower()) != 32:
            msg = "That does not appear to be a valid Client Secret"
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig)
            await setup12(message, user, guildconfig, *args)
        else:
            guildconfig.set('blizzard', 'client_secret', message.content)
            await guildconfig.write()
            await setup13(message, user, guildconfig, *args)


async def setup13(message, user, guildconfig, *args):
    user['setupstep'] = 13
    running_setup[user['user_id']] = user
    title = "Select a command prefix for bot commands:"
    embed = discord.Embed(title=title, color=HELP_COLOR)
    for num, cmd in COMMAND_PREFIXES.items():
        embed.add_field(name=f"{num}: {cmd[0]}", value=f"{cmd[1]}")
    await messagesend(message, embed, user, guildconfig)


async def response13(message, user, guildconfig, *args):
    resp = message.content
    try:
        int(resp)
    except:
        msg = f'Invalid selection.  Please select 1 through {len(COMMAND_PREFIXES)}'
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(message, embed, user, guildconfig)
        await setup13(message, user, guildconfig, *args)
    else:
        if int(resp) < 1 or int(resp) > len(COMMAND_PREFIXES):
            msg = f'Invalid selection.  Please select 1 through {len(COMMAND_PREFIXES)}'
            embed = discord.Embed(description=msg, color=FAIL_COLOR)
            await messagesend(message, embed, user, guildconfig)
            await setup13(message, user, guildconfig, *args)
        else:
            guildconfig.set('discord', 'command_prefix', COMMAND_PREFIXES[int(resp)][0])
            await guildconfig.write()
            del running_setup[user['user_id']]
            guildconfig.set("discord", "setupran", "True")
            guildconfig.set("discord", "setupadmin", user['user_name'])
            guildconfig.set("discord", "setupadmin_id", user['user_id'])
            await guildconfig.write()
            title = 'WowInfoClassic setup wizard complete!'
            embed = discord.Embed(title=title, color=HELP_COLOR)
            await messagesend(message, embed, user, guildconfig)


async def setting(message, user, guildconfig, *args):
    logcommand(message, user)
    try:
        embed = discord.Embed(title="WoWInfoClassic Bot Settings", description=f'Discord Server Name: **{user["guild_name"]}**', color=HELP_COLOR)
        for sec, val in guildconfig._sections.items():
            msg = ''
            for key, value in val.items():
                if key != 'admin_role_id' and key != 'user_role_id' and key != 'setupran' and key != 'server_slug' and key != 'server_locale' and key != 'server_region_id' and key != 'server_id' and key != 'limit_to_channel_id':
                    if key == 'api_key' or key == 'client_id' or key == 'client_secret':
                        if value != 'None':
                            value = '<secret>'
                    msg = msg + f'{key.title()}: **{value}**\n'
            embed.add_field(name=sec.capitalize(), value=msg, inline=False)
        await messagesend(message, embed, user, guildconfig)
    except:
        log.exception(f'Exception in settings function')
        await messagesend(message, error_embed(message), user, guildconfig)


async def admin(message, user, guildconfig, *args):
    if args:
        if args[0].startswith('con') or args[0] == 'servers':
            embed = discord.Embed(title=f"Servers Connected ({len(bot.guilds)})", description=f"Discord Latency: {truncate_float(bot.latency, 2)}", color=HELP_COLOR)
            for eguild in bot.guilds:
                guildconfig = GuildConfigParser(redis, str(eguild.id))
                await guildconfig.read()
                msg = f"ServerID: **{eguild.id}**\nRealm: **{guildconfig.get('server', 'server_category')}**\nGuild: **{guildconfig.get('server', 'guild_name')}**\nFaction: **{guildconfig.get('server', 'faction')}**\nTimezone: **{guildconfig.get('server', 'server_timezone')}**\nShardID: **{eguild.shard_id}**\nChunked: **{eguild.chunked}**\nClients: **{eguild.member_count}**\nSetup Ran? **{guildconfig.get('discord','setupran')}**\nSetup Admin: **{guildconfig.get('discord', 'setupadmin')}**\n\n"
                embed.add_field(name=f"{eguild.name}", value=msg)
            await message.author.send(embed=embed)
        if args[0] == 'invite':
            msg = 'https://discord.com/oauth2/authorize?bot_id=750867600250241086&scope=bot&permissions=8'
            embed = discord.Embed(description=msg, color=HELP_COLOR)
            await messagesend(message, embed, user, guildconfig)
    else:
        msg = f"You must specify an admin command"
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(message, embed, user, guildconfig)


async def help(message, user, guildconfig, *args):
    logcommand(message, user)
    command_prefix = guildconfig.get("discord", "command_prefix")
    if guildconfig.get("discord", "pm_only") == "True":
        msg = "Commands can be privately messaged directly to the bot, the reply will be in a private message."
    elif guildconfig.get("discord", "limit_to_channel") == 'Any':
        msg = "Commands can be privately messaged directly to the bot or in any channel, the reply will be in the channel you sent the command from."
    else:
        msg = f'Commands can be privately messaged directly to the bot or in the #{guildconfig.get("discord", "limit_to_channel")} channel, the reply will be in the #{guildconfig.get("discord", "limit_to_channel")} channel or a private message'
    embed = discord.Embed(title="WoW Info Classic Bot Commands:", description=msg, color=HELP_COLOR)
    embed.add_field(name=f"**`{command_prefix}raids [optional instance name]`**", value=f"Last 5 raids for the guild, [MC,ONY,BWL,ZG,AQ20,AQ40]\nLeave instance name blank for all", inline=False)
    embed.add_field(name=f"**`{command_prefix}player <character name>`**", value=f"Character information from last logged encounters", inline=False)
    embed.add_field(name=f"**`{command_prefix}gear <character name>`**", value=f"Character gear from last logged encounters", inline=False)
    embed.add_field(name=f"**`{command_prefix}price <item name>`**", value=f"Price and information for an item", inline=False)
    embed.add_field(name=f"**`{command_prefix}item <item name>`**", value=f"Same as price command", inline=False)
    embed.add_field(name=f"**`{command_prefix}server`**", value=f"Status and info of the World of Warcraft Classic server", inline=False)
    embed.add_field(name=f"**`{command_prefix}news`**", value=f"Latest World of Warcraft Classic News", inline=False)
    embed.add_field(name=f"**`{command_prefix}help`**", value=f"This help message", inline=False)
    if user['is_admin']:
        embed.add_field(name=f"**`{command_prefix}setup`**", value=f"Run the bot setup wizard (admins only)", inline=False)
        embed.add_field(name=f"**`{command_prefix}settings`**", value=f"Current bot settings (admins only)", inline=False)
    await message.author.send(embed=embed)


async def test(message, user, guildconfig, *args):
    logcommand(message, user)
    # blizcli = BlizzardAPI(bliz_int_client, bliz_int_secret, guildconfig.get("server", "server_region"))
    # await blizcli.authorize()
    # pprint(await blizcli.realm_list())
    pprint(guildconfig._sections)


def main():
    if BRANCH != 'develop':
        bot.run(discordkey)
    else:
        bot.run(discordkey_dev)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.info(f'Termination signal [KeyboardInterrupt] Closing web sessions.')
        log.info(f'Exiting.')
        exit(0)
        try:
            exit(0)
        except SystemExit:
            _exit(0)
    except:
        log.exception(f'Main Exception Caught!')
