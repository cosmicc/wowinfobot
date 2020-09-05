from warcraftlogs.client import WarcraftLogsClient
from warcraftlogs.models.characters import Gear, Talent, Spec, Class, Character
import datetime
from math import trunc

wclclient = WarcraftLogsClient("1a2425a5bcad0f89641bb3c78adeda5e")


item_slot = {0: 'Head', 1: 'Neck', 2: 'Shoulders', 3: 'Shirt', 4: 'Chest', 5: 'Belt', 6: 'Legs', 7: 'Boots', 8: 'Bracers', 9: 'Hands', 10: 'Ring', 11: 'Ring', 12: 'Trinket', 13: 'Trinket', 14: 'Back', 15: 'Main Hand', 16: 'Off-Hand', 17: 'Ranged', 18: 'Tabard'}

item_quality = {1: 'Common', 2: 'Uncommon', 3: 'Rare', 4: 'Epic', 5: 'Legendary', 6: 'Artifact'}

RZONE = {1005: "Ahn'Qiraj 40", 1002: "Blackwing Lair", 1004: "Ahn'Qiraj 20", 1000: "Molten Core", 1003: "Zul'Gurub", 1001: "Onyxia"}


intervals = (
    ("years", 31536000),
    ("months", 2592000),
    # ('weeks', 604800),  # 60 * 60 * 24 * 7
    ("days", 86400),  # 60 * 60 * 24
    ("hours", 3600),  # 60 * 60
    ("minutes", 60),
    ("seconds", 1),
)

def converttime(dtime):
    return datetime.datetime.fromtimestamp(tfixup(dtime)).strftime('%m/%d/%y %-I:%M%p') 

def converttime2(dtime):
    return datetime.datetime.fromtimestamp(tfixup(dtime)).strftime('%-I:%M%p')

def tfixup(dtime):
    return int(str(dtime)[:10])

def elapsedTime(start_time, stop_time, nowifmin=False, append=False):
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
    if tseconds < 60 and nowifmin:
        return "now"
    else:
        if append:
            return ", ".join(result[:granularity]) + f" {append}"
        else:
            return ", ".join(result[:granularity])

def truncate_float(number, digits):
    if not isinstance(number, (float, str)):
        number = float(number)
    if not isinstance(digits, int):
        raise TypeError(f"Digits value must be type int, not {type(digits)}")
    if isinstance(number, str):
        number = float(number)
    stepper = 10.0 ** abs(digits)
    return trunc(stepper * number) / stepper

def get_player_parses(player):
    retlist = []
    for each in rzone:
        retlist = client.parses(player.capitalize(), "Bigglesworth", "US", zone=each)
        if len(retlist) != 0:
            break;
    return retlist

def get_report_table(view, code):
    retlist = []
    retlist = client.tables(view, code)
    return retlist

def get_fights(code):
    retlist = []
    retlist = client.fights(code)
    return retlist

def get_player_parses(player):
    retlist = []
    enccount = 0
    lastraidlist = {((0, 0)): 0}}
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
                isthere = False
                rid = eee['reportID']
                starttime = eee['startTime']
                if rid not in lastraidlist:


                for key, value in eee.items():
                    if key == "startTime":
                        for k, v in laste.items():
                            if v == rid:
                                isthere = True
                                if tfixup(value) > k:
                                    del laste[k]
                                    laste.update({tfixup(value): {rid: eee}})
                        if value not in 
                if not isthere:
                    laste.update({tfixup(value): {rid: eee}})

                            
                        if tfixup(value) > min(laste): and rid not in laste[min(laste)]:
                            if len(laste) > 5:
                                del laste[min(laste)]
                            laste.update({tfixup(value): {rid: eee}})
            enccount = enccount + len(retlist)
            slist = [mccount, onycount, bwlcount, zgcount, aq20count, aq40count]
    if len(lretlist) == 0:
        msg = "Cannot find character {} in warcraft logs".format(player)
        #embed = discord.Embed(description=msg, color=FAIL_COLOR)
        #await messagesend(ctx, embed, allowgeneral=False, reject=True)
    return enccount, laste, slist


def get_gear(player):
    parselist = client.parses(player.capitalize(), "Bigglesworth", "US", zone=1000)
    for key, value in parselist[0].items():
        #print (key, value)
        if key == "reportID":
            reporttable = client.tables('casts', value, start=0, end=9999999)
    for key, value in reporttable.items():
        print(key, value)
        if key == 'entries':
            for eachp in value:
                for nkey, nval in eachp.items():
                    if nkey == 'name' and nval == player.capitalize():
                        pinfo = eachp
                        classspec = pinfo['icon']
    for kkey, kval in pinfo.items():
        if kkey == 'gear':
            pgear = kval
    
    return classspec, pgear
    #for item in pgear: 
    #    print(item)
        #    if key == "friendlies":
    #        for eeach in value:
    #            for nkey, nval in eeach.items():
    #                if nkey == 'id':
    #                    playerid = nkey

    #reporttable = client.tables(player.capitalize(), "Bigglesworth", "US", zone=1000)
#    for key, value in fightlist.items():

#print(get_fights('w1DFHA46Kd8rptTC'))
for key, val in get_player_parses('arbin')[1].items():
    print(key, val)
