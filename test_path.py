from pathlib import Path

logfile = Path('/home/ip/wowinfobot.log')

print(str(logfile))

newstem = logfile.stem + "-dev" + logfile.suffix

logfile = logfile.parent / newstem

print(str(logfile))
