import discord
from discord.ext import commands
from configparser import ConfigParser
from warcraftlogs.client import WarcraftLogsClient
from loguru import logger as log
import datetime
from math import trunc

configfile = '/etc/wowinfoclassic.cfg'
configdata = ConfigParser()
configdata.read(configfile)
wclapi = configdata.get("general", "warcraftlogs_apikey")
discordkey = configdata.get("general", "discord_apikey")

SUCCESS_COLOR = 0x00FF00
FAIL_COLOR = 0xFF0000
INFO_COLOR = 0x0088FF
HELP_COLOR = 0xFF8800
GEAR_ORDER = {1: 'Head', 2: 'Neck', 3: 'Shoulders', 4: 'Shirt', 5: 'Chest', 6: 'Belt', 7: 'Legs', 8: 'Boots', 9: 'Wrists', 10: 'Hands', 11: 'Ring', 12: 'Ring', 13: 'Trinket', 14: 'Trinket', 15: 'Back', 16: 'Main Hand', 17: 'Off Hand', 18: 'Ranged'}
BZONE = {1001: 1, 1003: 9, 1000: 10, 1004: 6, 1002: 8, 1005: 9}
RZONE = {1001: "Onyxia", 1003: "Zul'Gurub", 1000: "Molten Core", 1004: "Ahn'Qiraj 20", 1002: "Blackwing Lair", 1005: "Ahn'Qiraj 40"}
intervals = (
    ("years", 31536000),
    ("months", 2592000),
    # ('weeks', 604800),  # 60 * 60 * 24 * 7
    ("days", 86400),  # 60 * 60 * 24
    ("hours", 3600),  # 60 * 60
    ("minutes", 60),
    ("seconds", 1),
)

command_prefix = "?"
client = commands.Bot(command_prefix=command_prefix, case_insensitive=True)
client.remove_command("help")

wclclient = WarcraftLogsClient(wclapi)

def tfixup(dtime):
    tm = int(str(dtime)[:10])
    return tm - 28800


def converttime(dtime, timeonly=False, dateonly=False):
    if timeonly:
        return datetime.datetime.fromtimestamp(tfixup(dtime)).strftime('%-I:%M%p')
    elif dateonly:
        return datetime.datetime.fromtimestamp(tfixup(dtime)).strftime('%m/%d/%y')
    else:
        return datetime.datetime.fromtimestamp(tfixup(dtime)).strftime('%m/%d/%y %-I:%M%p')

def elapsedTime(start_time, stop_time, append=False):
    result = []
    if start_time > stop_time:
        seconds = int(start_time) - int(stop_time)
    else:
        seconds = int(stop_time) - int(start_time)
    tseconds = seconds
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

@client.event
async def on_ready():
        log.log("SUCCESS", f"Discord logged in as {client.user.name} id {client.user.id}")
        activity = discord.Game(name="Comming Soon!")
        try:
            await client.change_presence(
                status=discord.Status.online, activity=activity
            )
        except:
            log.error("Exiting")

def truncate_float(number, digits):
    if not isinstance(number, (float, str)):
        number = float(number)
    if not isinstance(digits, int):
        raise TypeError(f"Digits value must be type int, not {type(digits)}")
    if isinstance(number, str):
        number = float(number)
    stepper = 10.0 ** abs(digits)
    return trunc(stepper * number) / stepper


async def get_player_parses(ctx, player):
    retlist = []
    enccount = 0
    laste = 0
    lretlist = []
    mccount = 0
    bwlcount = 0
    aq40count = 0
    aq20count = 0
    zgcount = 0
    onycount = 0
    for kkey, vval in RZONE.items():
        retlist = wclclient.parses(player.capitalize(), "Bigglesworth", "US", zone=kkey)
        if len(retlist) != 0:
            if kkey == 1000:
                mccount = len(retlist)
            elif kkey == 1001:
                onycount = len(retlist)
            elif kkey == 1002:
                bwlcount = len(retlist)
            elif kkey == 1003:
                zgcount = len(retlist)
            elif kkey == 1004:
                aq20count = len(retlist)
            elif kkey == 1005:
                aq40count = len(retlist)
            for eee in retlist:
                for key, value in eee.items():
                    if key == "startTime":
                        if tfixup(value) > laste:
                            laste = tfixup(value)
                            lretlist = [eee] 
            enccount = enccount + len(retlist)
            slist = [mccount, onycount, bwlcount, zgcount, aq20count, aq40count]
    if len(lretlist) == 0:
        msg = "Cannot find character {} in warcraft logs".format(player)
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(ctx, embed, allowgeneral=False, reject=True)
    return lretlist, enccount, slist

def fight_data(fid):
    a = wclclient.fights(fid)
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
    log.log("INFO",f"Responding to [{ctx.message.content}] request from [{ctx.message.author}] in [#{dchan}]",)
    return True

async def messagesend(ctx, embed, allowgeneral=False, reject=True, adminonly=False):
    try:
        if type(ctx.message.channel) == discord.channel.DMChannel:
            return await ctx.message.author.send(embed=embed)
        elif str(ctx.message.channel) != "bot-channel" or (
            not allowgeneral and str(ctx.message.channel) == "general"
        ):
            role = str(
                discord.utils.get(ctx.message.author.roles, name="admin")
            )
            #if role != "admin":
            #    await ctx.message.delete()
            #if reject and role != "admin":
            #    rejectembed = discord.Embed(description=rejectmsg, color=HELP_COLOR)
            #    return await ctx.message.author.send(embed=rejectembed)
            #elif role != "admin":
            #    return await ctx.message.author.send(embed=embed)
            #else:
            return await ctx.message.channel.send(embed=embed)
        else:
            return await ctx.message.channel.send(embed=embed)
    except:
        log.exception("Critical error in message send")

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
        else:
            log.critical(f"discord bot error for {ctx.message.author}: {ctx.message.content} - {error}")
    except:
        log.exception("command error: ")

@client.command(name="last", aliases=["lastraid", "lastraids", "raids"])
@commands.check(logcommand)
async def lastraids(ctx, *args):
    enclist = wclclient.guild("Consortium", "Bigglesworth", "US")
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
            await ctx.send(f"Invalid instance {args[0]}")
    if tt == 0:
        tttitle = "Last 5 Logged Raids for Consortium"
    else:
        tttitle = f"Last 5 Logged {tt} Raids for Consortium"
    embed = discord.Embed(title=tttitle, color=INFO_COLOR)
    for each in enclist:
        if (each['zone'] == nzone or nzone == 0) and (a <= 5):
            kills, wipes, size, lastboss = fight_data(each['id'])
            embed.add_field(name=f"{RZONE[each['zone']]} - {converttime(each['start'], dateonly=True)} ({each['title']})", value=f"{converttime(each['start'], timeonly=True)}-{converttime(each['end'], timeonly=True)} - {elapsedTime(tfixup(each['start']), tfixup(each['end']))}\n[Bosses Killed: ({kills}\{BZONE[each['zone']]}) with {wipes} Wipes - Last Boss: {lastboss}](https://classic.warcraftlogs.com/reports/{each['id']})", inline=False)
            a = a + 1
    if a == 1:
        b = 'No information was found'
    await messagesend(ctx, embed, allowgeneral=True, reject=False)


@client.command(name="info", aliases=["player", "playerinfo"])
@commands.check(logcommand)
async def info(ctx, *args):
    if args:
        retlist, enccount, slist = await get_player_parses(ctx, args[0])
        if len(retlist) != 0:
            gg = ""
            il = []
            en = 0
            ila = ""
            for key, value in retlist[len(retlist)-1].items():
                if key == "gear":
                    for gear in value:
                        if 'itemLevel' in gear:
                            il.append(int(gear['itemLevel']))
                        else:
                            ila = "Not Available"
                        if 'permanentEnchant' in gear:
                            if gear['permanentEnchant'] != "0":
                                en = en + 1
                        else:
                            enchants = "Not Available"
            if len(il) > 0:
                newil = [i for i in il if i >= 20]
                ila = int(sum(newil) / len(newil))
            if en == 0:
                ench = "Not Avalable"
            else:
                ench = f"{en} of (9 to 11)"
            for key, value in retlist[len(retlist)-1].items():
                if key == "encounterName":
                    gf = f"Last Encounter: {value} on "
                if key == "startTime":
                    gf = gf + f"{converttime(value)}\n"
                if key == "reportID":
                    reportid = value
                    embed = discord.Embed(title=gf, color=INFO_COLOR, url=f"https://classic.warcraftlogs.com/reports/{reportid}")
                if key == "class":
                    pclass = value 
                if key == "spec":
                    spec = value
                if key == "percentile":
                    perc = value
                if key == "rank":
                    rank = value
                if key == "outOf":
                    outof = value
            embed.set_author(name=args[0].capitalize())
            embed.add_field(name=f"Class:", value=f"{pclass}")
            embed.add_field(name=f"Spec:", value=f"{spec}")
            embed.add_field(name=f"Gear Enchants:", value=f"{ench}")
            embed.add_field(name=f"Avg Item Level for fight:", value=f"{ila}")
            embed.add_field(name=f"Last Fight Percentile:", value=f"{truncate_float(perc, 1)}%")
            embed.add_field(name=f"Last Fight Rank:", value="{:,} of {:,}".format(rank, outof))
            embed.add_field(name=f"Encounters Logged:", value=f"{enccount}")
            embed.add_field(name=f"MC Bosses Logged:", value=f"{slist[0]}")
            embed.add_field(name=f"Ony Raids Logged:", value=f"{slist[1]}")
            embed.add_field(name=f"BWL Bosses Logged:", value=f"{slist[2]}")
            embed.add_field(name=f"ZG Bosses Logged:", value=f"{slist[3]}")
            embed.add_field(name=f"AQ20 Bosses Logged:", value=f"{slist[4]}")
            embed.add_field(name=f"AQ40 Bosses Logged:", value=f"{slist[5]}")
            await messagesend(ctx, embed, allowgeneral=True, reject=False)
    else:
        msg = f"You must specify a game character to get info for"
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(ctx, embed, allowgeneral=False, reject=True)


@client.command(name="gear", aliases=["playergear"])
@commands.check(logcommand)
async def gear(ctx, *args):
    if args:
        retlist, enccount, slist = await get_player_parses(ctx, args[0])
        o = 1
        lil = []
        if len(retlist) != 0:
            for key, value in retlist[len(retlist)-1].items():
                if key == "reportID":
                    reportid = value
                if key == "encounterName":
                    mob = value
                if key == "startTime":
                    edate = converttime(value, dateonly=True)
            msg = f"Gear on {args[0].capitalize()} from last encounter: {mob} on {edate}"
            embed = discord.Embed(title=msg, color=INFO_COLOR, url=f"https://classic.warcraftlogs.com/reports/{reportid}")
            for key, value in retlist[len(retlist)-1].items():
                if key == "gear":
                    for gear in value:
                        if 'itemLevel' in gear:
                            il = gear['itemLevel']
                            lil.append(gear['itemLevel'])
                        else:
                            il = gear['quality']
                        if 'permanentEnchant' in gear:
                            gg = gg + "{}<https://www.wowhead.com/item={}> ({}) Enchant: {}\n".format(gear['name'], gear['id'], il, gear['permanentEnchant'])
                        else:
                            if o != 4:
                                embed.add_field(name=f"{GEAR_ORDER[o]} ({il.capitalize()}):", value=f"[{gear['name']}](https://classic.wowhead.com/item={gear['id']})")
                            o = o + 1
            await messagesend(ctx, embed, allowgeneral=True, reject=False)
    else:
        msg = f"You must specify a game character to list gear for"
        embed = discord.Embed(description=msg, color=FAIL_COLOR)
        await messagesend(ctx, embed, allowgeneral=False, reject=True)


@client.command(name="help", aliases=["helpme", "commands"])
@commands.check(logcommand)
async def help(ctx):
    msg = "Commands can be privately messaged directly to the bot or in channels"
    embed = discord.Embed(title="WoW Info Classic Bot Commands:", description=msg, color=HELP_COLOR)
    embed.add_field(name=f"**`{command_prefix}raids [optional instance name]`**", value=f"Last 5 raids for the guild, [MC,ONY,BWL,ZG,AQ20,AQ40]\nLeave instance name blank for all", inline=False)
    embed.add_field(name=f"**`{command_prefix}info [character name]`**", value=f"Character information from last encounter logged", inline=False)
    embed.add_field(name=f"**`{command_prefix}gear [character name]`**", value=f"Worn gear from last encounter logged", inline=False)

    await ctx.message.author.send(embed=embed)
    if (type(ctx.message.channel) != discord.channel.DMChannel and str(ctx.message.channel) != "bot-channel"):
        await ctx.message.delete()

client.run(discordkey)

