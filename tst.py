import random

a = {15000: 'moo', 16000: 'foo'}
b = {}

new = [(14000, 'lklklk'), (16500, 'ooooo'), (12000, 'kkk'), (18000, 'ooooo'), (16200, 'poop'), (19000, 'ooooo'),(18001, 'poop'), (21001, 'fpoop'), (18002, 'toop'), (22001, 'poop'), (30001, 'pooped'),]

print(a)

for eee in new:
    #print(f'trying {eee[0]}')
    #print(f'current min: {min(a.copy())}')
    if eee[0] > min(a):
        #print(f'{eee[0]} > {ref}')
        if eee[1] in b:
            #print(f'{eee[1]} in {b}')
            #print(f'del {b[eee[1]]}')
            del a[b[eee[1]]]
            del b[eee[1]]
            a.update({eee[0]: str(random.randint(10000, 50000))})
            b.update({eee[1]: eee[0]})
            #print(f'finished: {a}')
        else:
            #print(f'{eee[1]} NOT in {b}')
            a.update({eee[0]: str(random.randint(10000, 50000))})
            b.update({eee[1]: eee[0]})
            if len(a) > 5:
                del a[min(a)]
            #print(f'finished: {a}')
    #else:
        #print(f'skipping {eee[0]}')

print(" ")

print(a)
print(b)


