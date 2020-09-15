import msgpack

tat = False

a = msgpack.packb(tat)
b = msgpack.unpackb(a)

print(type(b))
