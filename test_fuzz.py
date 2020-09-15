from fuzzywuzzy import fuzz
from prettyprinter import pprint

commands = ('player', 'item', 'raids', 'news', 'settings', 'admin', 'gear')

fuzzy_command_error = 75

def keywithmaxval(d, command):
     v=list(d.values())
     k=list(d.keys())
     if max(v) >= fuzzy_command_error:
        if max(v) != 100:
            print(f'Fuzzy command fixed [{command}] [{max(v)}%]')
        return k[v.index(max(v))]
     else:
        return None

def cmdsearch(val):
    ratios = {}
    for command in commands:
        ratio = fuzz.ratio(command, val)
        ratios[command] = ratio
    #pprint(sorted(ratios.items()))
    return keywithmaxval(ratios, val)


while True:
    val = input("Command: ")
    print(cmdsearch(val))
