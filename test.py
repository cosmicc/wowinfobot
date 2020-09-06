from warcraftlogs.client import WarcraftLogsClient
from warcraftlogs.models.characters import Gear, Talent, Spec, Class, Character
import datetime
from math import trunc
from prettyprinter import pprint

wclclient = WarcraftLogsClient("1a2425a5bcad0f89641bb3c78adeda5e")


item_slot = {0: 'Head', 1: 'Neck', 2: 'Shoulders', 3: 'Shirt', 4: 'Chest', 5: 'Belt', 6: 'Legs', 7: 'Boots', 8: 'Bracers', 9: 'Hands', 10: 'Ring', 11: 'Ring', 12: 'Trinket', 13: 'Trinket', 14: 'Back', 15: 'Main Hand', 16: 'Off-Hand', 17: 'Ranged', 18: 'Tabard'}

item_quality = {1: 'Common', 2: 'Uncommon', 3: 'Rare', 4: 'Epic', 5: 'Legendary', 6: 'Artifact'}

ROLES = ['Tank', 'Healer', 'DPS']

RZONE = {1005: "Ahn'Qiraj 40", 1002: "Blackwing Lair", 1004: "Ahn'Qiraj 20", 1000: "Molten Core", 1003: "Zul'Gurub", 1001: "Onyxia"}

BOSSREF = {'Onyxia': 1001, 'Ragnaros': 1000, 'Lucifron': 1000, 'Magmadar': 1000, 'Gehennas': 1000, 'Garr': 1000, 'Baron Geddon': 1000, 'Shazzrah': 1000, 'Sulfuron Harbinger': 1000, 'Golemagg the Incinerator': 1000, 'Majordomo Executus': 1000, 'Ossirian the Unscarred': 1004, 'Ayamiss the Hunter': 1004, 'Buru the Gorger': 1004, 'Moam': 1004, 'General Rajaxx': 1004, 'Kurinnaxx': 1004, 'Nefarian': 1002, 'Chromaggus': 1000, "Jin'do the Hexxer": 1003, 'High Priest Thekal': 1003, "C'Thun": 1005, 'Ouro': 1005, 'Hakkar': 1003}

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


def converttime(dtime, timeonly=False, dateonly=False):
    if timeonly:
        return datetime.datetime.fromtimestamp(tfixup(dtime)).strftime('%-I:%M%p')
    elif dateonly:
        return datetime.datetime.fromtimestamp(tfixup(dtime)).strftime('%m/%d/%y')
    else:
        return datetime.datetime.fromtimestamp(tfixup(dtime)).strftime('%m/%d/%y %-I:%M%p')

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


def clean_last_encounters(encounters):
    elen = len(encounters) - 1
    while elen >= 0:
        print(RZONE[BOSSREF[encounters[elen][1]['encounterName']]], converttime(encounters[elen][1]['startTime'], dateonly=True))
        elen = elen - 1




class Player:

    def filter_last_encounters(self, npl):
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
        self.playerclass = ""
        self.playerspec = ""
        self.playerrole = ""
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
        self.geardate = ""
        self.edl = {0: 0}
        self.tpl = {0: 0}
        for kkey, vval in RZONE.items():
            parselist = wclclient.parses(self.playername, "Bigglesworth", "US", zone=kkey)
            if len(parselist) != 0 and 'error' not in parselist:
                if kkey == 1000:
                    self.totalencounters = self.totalencounters + len(parselist)
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
                self.filter_last_encounters(parselist)
        if self.totalencounters > 0:
            self.exists = True
        else:
            return None
        self.lastencounters = sorted(self.edl.items())
        for encounter in self.lastencounters:
            if encounter[1] != 0:
                if 'class' in encounter[1] and self.playerclass == "":
                    self.playerclass = encounter[1]['class']
                if 'spec' in encounter[1] and self.playerspec == "":
                    if encounter[1]['spec'] not in ROLES:
                        self.playerspec = encounter[1]['spec']
                    else:
                        self.playerrole = encounter[1]['spec']
                reporttable = wclclient.tables('casts', encounter[1]['reportID'], start=0, end=18000)
                for entry in reporttable['entries']:
                    if entry['name'] == self.playername:
                        if 'spec' in entry and self.playerspec == "":
                            self.playerspec = entry['spec']
                        if 'icon' in entry and self.playerspec == "" and len(entry['icon'].split('-')) == 2:
                            self.playerclass = entry['icon'].split('-')[0]
                            self.playerspec = entry['icon'].split('-')[1]
                        if 'class' in entry and self.playerclass == "":
                            self.playerclass = entry['class']
                        if 'itemLevel' in entry and self.gearlevel == 0:
                            self.gearlevel = entry['itemLevel']
                        if 'gear' in entry:
                            if len(entry['gear']) > 1:
                                zone = BOSSREF[encounter[1]['encounterName']]
                                if zone == 1005:
                                    self.gearlist = entry['gear']
                                    self.geardate = converttime(encounter[1]['startTime'], dateonly=True)
                                elif len(self.gearlist) < 1:
                                    self.gearlist = entry['gear']
                                    self.geardate = converttime(encounter[1]['startTime'], dateonly=True)
        self.lastencounter = self.lastencounters[len(self.lastencounters) - 1][1]




player = Player('arbin')
print(f'Name: {player.playername}')
print(f'Class: {player.playerclass}')
print(f'Spec: {player.playerspec}')
print(f'Role: {player.playerrole}')
print(f'Gear Level: {player.gearlevel}')
print(f'Gear List: {player.gearlist}')
print(f'Gear Date: {player.geardate}')
clean_last_encounters(player.lastencounters)
