import signal
import sys
from configparser import ConfigParser
from datetime import datetime, timedelta
from math import trunc
# from prettyprinter import pprint
from numbers import Number

import discord
from discord.ext import commands
from loguru import logger as log

from apifetch import NexusAPI, WarcraftLogsAPI

configfile = '/etc/wowinfobot.cfg'
configdata = ConfigParser()
configdata.read(configfile)
wcl_api = configdata.get("warcraftlogs", "api_key")
command_prefix = configdata.get("discord", "command_prefix")
discordkey = configdata.get("discord", "api_key")
server = configdata.get("warcraft", "server_name").capitalize()
region = configdata.get("warcraft", "server_region").upper()
guild = configdata.get("warcraft", "guild_name").capitalize()
faction = configdata.get("warcraft", "faction").capitalize()
tsm_url = configdata.get("tsm", "api_url")
wcl_url = configdata.get("warcraftlogs", "api_url")
logfile = configdata.get("general", "logfile")
loglevel = configdata.get("general", "loglevel")

log.add(sink=str(logfile), level=loglevel, buffering=1, enqueue=True, backtrace=True, diagnose=True, serialize=False, delay=False, rotation="5 MB", retention="1 month", compression="tar.gz")

client = commands.Bot(command_prefix=command_prefix, case_insensitive=True)
client.remove_command("help")

wclclient = WarcraftLogsAPI(wcl_url, wcl_api)
tsmclient = NexusAPI(tsm_url)

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


def tfixup(dtime):
    tm = int(str(dtime)[:10])
    return tm - 28800


def convert_time(dtime, timeonly=False, dateonly=False):
    if timeonly:
        return datetime.fromtimestamp(tfixup(dtime)).strftime('%-I:%M%p')
    elif dateonly:
        return datetime.fromtimestamp(tfixup(dtime)).strftime('%m/%d/%y')
    else:
        return datetime.fromtimestamp(tfixup(dtime)).strftime('%m/%d/%y %-I:%M%p')


def fix_item_time(rawtime):
    date_obj = datetime.strptime(rawtime, '%Y-%m-%dT%H:%M:%S.000Z')
    date_adj = date_obj - timedelta(hours=8)
    return date_adj.strftime('%m-%d-%y %I:%M %p')


def fix_news_time(rawtime):
    date_obj = datetime.strptime(rawtime, '%a, %d %b %Y %H:%M:%S -0500')
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


def filter_details(name, tags, labels):
    details = []
    for line in labels:
        label = line['label']
        if label != 'Sell Price:' and not label.startswith('Item Level') and not label.startswith('Requires Level') and label not in tags and label != name:
            details.append(label)
    return details


class Item:

    def __init__(self, itemid):
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
        itemdata = await tsmclient.price(self.id, server.lower(), faction.lower())
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
            if tfixup(entry['startTime']) > min(self.edl):
                if entry['reportID'] in self.tpl:
                    del self.edl[self.tpl[entry["reportID"]]]
                    del self.tpl[entry["reportID"]]
                    self.edl.update({tfixup(entry["startTime"]): entry})
                    self.tpl.update({entry["reportID"]: tfixup(entry["startTime"])})
                else:
                    self.edl.update({tfixup(entry["startTime"]): entry})
                    self.tpl.update({entry["reportID"]: tfixup(entry["startTime"])})
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
            parselist = await wclclient.parses(self.playername, server, region, zone=kkey)
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
                    reporttable = await wclclient.tables('casts', encounter[1]['reportID'], start=0, end=18000)
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


@client.event
async def on_ready():
        log.log("SUCCESS", f"Discord logged in as {client.user.name} id {client.user.id}")
        activity = discord.Game(name="Type ?help")
        try:
            await client.change_presence(status=discord.Status.online, activity=activity)
        except:
            log.error("Exiting")


async def fight_data(fid):
    a = await wclclient.fights(fid)
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


async def messagesend(ctx, embed, allowgeneral=False, reject=True, adminonly=False):
    try:
        if type(ctx.message.channel) == discord.channel.DMChannel:
            return await ctx.message.author.send(embed=embed)
        #elif str(ctx.message.channel) != "bot-channel" or (not allowgeneral and str(ctx.message.channel) == "general"):
        #    role = str(discord.utils.get(ctx.message.author.roles, name="admin"))
            #if role != "admin":
            #    await ctx.message.delete()
            #if reject and role != "admin":
            #    rejectembed = discord.Embed(description=rejectmsg, color=HELP_COLOR)
            #    return await ctx.message.author.send(embed=rejectembed)
            #elif role != "admin":
            #    return await ctx.message.author.send(embed=embed)
            #else:
        #    return await ctx.message.channel.send(embed=embed)
        else:
            return await ctx.message.channel.send(embed=embed)
    except:
        log.exception("Critical error in message send")

'''
@client.event
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
            #await messagesend(ctx, embed, allowgeneral=True, reject=False)
        else:
            log.exception(f"discord bot error for {ctx.message.author}: {ctx.message.content} - {error}")
            embed = discord.Embed(description="**An error has occurred, contact Arbin.**", color=FAIL_COLOR)
            #await messagesend(ctx, embed, allowgeneral=True, reject=False)
    except:
        log.exception("command error: ")

'''


@client.command(name="last", aliases=["lastraid", "lastraids", "raids"])
@commands.check(logcommand)
async def lastraids(ctx, *args):
    embed = discord.Embed(description="**Please wait, fetching information...**", color=INFO_COLOR)
    respo = await messagesend(ctx, embed, allowgeneral=True, reject=False)
    enclist = await wclclient.guild(guild, server, region)
    a = 1
    b = ''
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
            embed.add_field(name=f"{RZONE[each['zone']]} - {convert_time(each['start'], dateonly=True)} ({each['title']})", value=f"{convert_time (each['start'], timeonly=True)}-{convert_time(each['end'], timeonly=True)} - {elapsedTime(tfixup(each['start']), tfixup(each['end']))}\n[Bosses Killed: ({kills}\{BZONE[each['zone']]}) with {wipes} Wipes - Last Boss: {lastboss}](https://classic.warcraftlogs.com/reports/{each['id']})", inline=False)
            a = a + 1
    if a == 1:
        b = 'No information was found'
    await respo.delete()
    await messagesend(ctx, embed, allowgeneral=True, reject=False)


@client.command(name="news", aliases=["wownews", "warcraftnews"])
@commands.check(logcommand)
async def news(ctx, *args):
    embed = discord.Embed(description="Please wait, fetching information...", color=INFO_COLOR)
    respo = await messagesend(ctx, embed, allowgeneral=True, reject=False)
    news = await tsmclient.news()
    embed = discord.Embed(title=f'World of Warcraft Classic News', color=INFO_COLOR)
    for each in news:
        embed.add_field(name=f"**{each['title']}**", value=f"{fix_news_time(each['pubDate'])}\n[{each['content']}]({each['link']})", inline=False)
    await respo.delete()
    await messagesend(ctx, embed, allowgeneral=True, reject=False)


@client.command(name="info", aliases=["player", "playerinfo"])
@commands.check(logcommand)
async def info(ctx, *args):
    if args:
        embed = discord.Embed(description="Please wait, fetching information...", color=INFO_COLOR)
        respo = await messagesend(ctx, embed, allowgeneral=True, reject=False)
        player = Player(args[0])
        await player.fetch()
        if player.exists:
            embed = discord.Embed(title=f'{args[0].capitalize()} on {region}-{server}', color=INFO_COLOR)
            #embed.set_author(name=args[0].capitalize())
            embed.add_field(name=f"Class:", value=f"{player.playerclass}")
            embed.add_field(name=f"Spec:", value=f"{player.playerspec}")
            embed.add_field(name=f"Role:", value=f"{player.playerrole}")
            #embed.add_field(name=f"Gear Enchants:", value=f"{}")
            #embed.add_field(name=f"Avg Item Level for fight:", value=f"{")
            #embed.add_field(name=f"Last Fight Percentile:", value=f"{truncate_float(perc, 1)}%")
            #embed.add_field(name=f"Last Fight Rank:", value="{:,} of {:,}".format(rank, outof))
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


@client.command(name="gear", aliases=["playergear"])
@commands.check(logcommand)
async def gear(ctx, *args):
    if args:
        embed = discord.Embed(description="Please wait, fetching information...", color=INFO_COLOR)
        respo = await messagesend(ctx, embed, allowgeneral=True, reject=False)
        player = Player(args[0])
        pres = await player.fetch()
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


@client.command(name="item", aliases=["price", "itemprice"])
@commands.check(logcommand)
async def item(ctx, *args):
    if args:
        embed = discord.Embed(description="Please wait, fetching information...", color=INFO_COLOR)
        respo = await messagesend(ctx, embed, allowgeneral=True, reject=False)
        if not isinstance(args[0], Number):
            argstring = ' '.join(args)
            itemdata = await tsmclient.search(query=argstring, limit=1)
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


@client.command(name="help", aliases=["helpme", "commands"])
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

client.run(discordkey)
