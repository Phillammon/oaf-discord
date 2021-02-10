import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from libkol import Session
import os
import pickle

from db import db, User, Raid, Log, PriorActivity
from Verification import Verification
from Whitelist import Whitelist
from RaidLogs import RaidLogs
from OAF import OAF
from Stop import Stop

load_dotenv()

discord_admin_id = 663542786850816014

clans = [
    #("The Hogs of Destiny", 21459),
    ("The Hogs of Exploitery", 74403, ["hoe"]),
    ("The 100% of Scientific FACT Club", 84380, []),
    ("KirbyLlama's Private Dungeon Clan", 2046997188, []),
    ("Castle Greyhawk", 2046989105, []),
    ("I have no idea what's going on", 2046999422, []),
    ("Collaborative Dungeon Running 1", 2047008362, ["dungeon1"]),
    ("Collaborative Dungeon Running 2", 2047008363, ["dungeon2"])
]

async def main():
    db.init(os.getenv("DB"))
    db.connect()
    db.create_tables([User, Raid, Log, PriorActivity])

    async with Session() as kol:
        await kol.login(os.getenv("KOL_USER"), os.getenv("KOL_PASS"))
        cache = pickle.load(open( "oaf.cache", "rb" ))
        bot = commands.Bot("!")
        bot.kol = kol
        bot.raid_guild = int(os.getenv("DISCORD_GUILD"))
        bot.raid_channel = int(os.getenv("DISCORD_CHANNEL"))
        bot.add_cog(Verification(bot))
        bot.add_cog(RaidLogs(bot, clans))
        bot.add_cog(Whitelist(bot, clans))
        bot.add_cog(OAF(bot, cache))
        bot.add_cog(Stop(bot))
        await bot.login(os.getenv("DISCORD_TOKEN"))
        await bot.connect()
        pickle.dump(cache, open( "oaf.cache", "wb" ))


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
