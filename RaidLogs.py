from discord.ext import commands
from discord.utils import get
from libkol import Clan
from libkol.request.clan_raid_log import RaidAction
from libkol.Error import ClanPermissionsError
from time import time
from datetime import datetime, timedelta
from tqdm import tqdm
from peewee import SQL, JOIN, fn
import asyncio
import json
import re
import traceback
from tabulate import tabulate
import sys

from dotenv import load_dotenv
import os

from DiscordIO import DiscordIO
from util import pm_only, team_only
from db import db, Raid, Log, PriorActivity



load_dotenv()

extraclans = [
    ("The Hogs of Destiny", 21459, ["hod"]),
    ("Time Wasters", 48971, ["timewasters"]),
    ("Castle Greyhawk", 2046989105, ["grey"]),
    ("I have no idea what's going on", 2046999422, ["idea"])
]

excluded_clans = [
    ("Castle Greyhawk", 2046989105, ["grey"]),
    ("I have no idea what's going on", 2046999422, ["idea"])
]
        
excluded = [
    "The Dictator", "kirByllAmA",
    "kenny kamAKAzi", "Captain Scotch", 
    "gregmasta", "violetinsane", 
    "RandomExtremity", "madowl",
    "Gausie", "threebullethamburgler",
    "Just Eyes", "Phillammon",
    "Headdab", "stibarsen",
    "NatNit", "monsieur bob",
    "coolanybody", "stockFD3S",
    "ast154251", "Archie700",
    "k3wLb0t", "aEniMUs",
    "tHE eROsIoNseEker", "worthawholebean",
    "phreddrickkv2", "epicgamer",
    "monkeyman200"
]

excluded_list = [x.lower() for x in excluded]

kills_pattern = re.compile(r"Your clan has defeated ([0-9]+) monster\(s\) in the ([A-Za-z]+).")

banish_locations = {
    ("forest", "cold"): "(Burrows -> Cold -> Read the heart a story)",
    ("forest", "hot"): "(Burrows -> Heat -> Pull the cork)",
    ("forest", "sleaze"): "(Tallest tree -> Climb -> Kick the nest (requires muscle class))",
    ("forest", "spooky"): "(Cabin -> Attic -> Music box (accordion thief preferred))",
    ("forest", "stench"): "(Cabin -> Kitchen -> Disposal)",
    ("village", "cold"): "(Square -> Blacksmith's -> Stoke the furnace)",
    ("village", "hot"): "(Duke's Estate -> Servant's quarters -> Turn off the ovens)",
    ("village", "sleaze"): "(Skid Row -> Tenements -> Paint over graffiti)",
    ("village", "spooky"): "(Square -> Gallows -> Paint the noose)",
    ("village", "stench"): "(Skid Row -> Sewers -> Unclog the grate)",
    ("castle", "cold"): "(Great Hall -> Kitchen -> Turn down freezer)",
    ("castle", "hot"): "(Dungeons -> Boiler Room -> Let off steam)",
    ("castle", "sleaze"): "(Tower -> Bedroom -> Parrot)",
    ("castle", "spooky"): "(Dungeons -> Cell Block -> Flush toilet)",
    ("castle", "stench"): "(Great Hall -> Dining Room -> Clear dishes)"
}

class RaidLogs(commands.Cog):
    def __init__(self, bot: commands.Bot, clans=[]):
        self.bot = bot
        self.clans = clans
        self.allclans = clans + extraclans
        # self.bg_task = self.bot.loop.create_task(self.monitor_clans(clans))

    async def get_channel(self, context, channel_name: str):
        if channel_name is None:
            return None

        try:
            return next(c for c in self.bot.get_all_channels() if c.name == channel_name)
        except StopIteration:
            await context.send("Cannot find a channel called {}".format(channel_name))
            return None

    async def parse_clan_raid_logs(self, clan_details, message_stream = sys.stdout):
        clan_name, clan_id, aliases = clan_details
        kol = self.bot.kol

        clan = Clan(kol, id=clan_id)
        await clan.join()

        try:
            current = await clan.get_raids()
        except ClanPermissionsError:
            message_stream.write("Skipping {} due to lack of basement permissions".format(clan_name))
            return

        try:
            previous = await clan.get_previous_raids()
        except:
            previous = []
            pass

        tasks = []
        created_raids = []
        updated_raids = []

        for data in tqdm(current + previous, desc="Discovering previous raid logs in {}".format(clan_name), file=message_stream, unit="raid logs", leave=False):
            raid = Raid.get_or_none(id=data.id)

            raids_list = updated_raids

            if raid is None:
                raid = Raid(id=data.id, name=data.name, clan_id=clan_id, clan_name=clan_name)
                raids_list = created_raids

            if data.events is None and raid.end is None:
                raid.start = data.start
                raid.end = data.end
                tasks += [asyncio.ensure_future(clan.get_raid_log(data.id))]

            if raid.is_dirty():
                raids_list.append(raid)

        Raid.bulk_create(created_raids, batch_size=50)
        Raid.bulk_update(updated_raids, fields=[Raid.start, Raid.end], batch_size=50)

        raids_data = current + [await t for t in tqdm(asyncio.as_completed(tasks), desc="Loading previous raid logs in {}".format(clan_name), unit="raid logs", total=len(tasks), leave=False, file=message_stream, ascii=False)]

        with tqdm(raids_data, desc="Parsing raid logs in {}".format(clan_name), unit="raids", file=message_stream, ascii=False) as p:
            for data in p:
                raid = Raid.get_or_none(id=data.id)

                if raid is None:
                    p.write("Something went wrong with raid {}".format(data.id))
                    continue

                logs = []

                for category, events in data.events:
                    category = category.rstrip(":")
                    for event in events:
                        turns = int(event.data.pop("turns", 0))

                        event_data = json.dumps(event.data, sort_keys=True)

                        log = Log.get_or_none(
                            Log.raid == raid,
                            Log.category == category,
                            Log.action == event.action,
                            Log.username == event.username,
                            Log.user_id == event.user_id,
                            Log.data == event_data
                        )

                        if log is None:
                            log = Log(
                                raid=raid,
                                category=category,
                                action=event.action,
                                username=event.username,
                                user_id=event.user_id,
                                turns=turns,
                                data=event_data,
                            )
                        elif log.turns != turns:
                            log.turns = turns
                            log.last_updated = time()

                        logs.append(log)

                with db.atomic():
                    Log.delete().where(Log.raid == raid).execute()
                    Log.bulk_create(logs, batch_size=50)
                    raid.summary = json.dumps(data.summary)
                    raid.save()


    async def monitor_clans(self, clans):
        kol = self.bot.kol
        await kol.login(os.getenv("KOL_USER"), os.getenv("KOL_PASS"))
        try:
            bot = self.bot
            await bot.wait_until_ready()

            if len(clans) == 0:
                clans = [(bot.kol.state["clan_name"], bot.kol.state["clan_id"], [])]

            for clan in clans:
                await self.parse_clan_raid_logs(clan)

        except Exception:
            print(traceback.format_exc())
            
    
    @team_only()
    @commands.command(name="parse_raids")
    async def parse_clans(self, context):
        kol = self.bot.kol
        await kol.login(os.getenv("KOL_USER"), os.getenv("KOL_PASS"))
        message = await context.send("Initializing display")
        message_stream = DiscordIO(message)
        for clan in self.allclans:
            await self.parse_clan_raid_logs(clan, message_stream)
        message_stream.print("Raid parsing complete")


    @commands.command(name="skills")
    #@pm_only()
    async def skills(self, context, recheck = True, send_message = True, since: str = "2019-06-06", limit: int = None, channel_name: str = None):
        channel = await self.get_channel(context, channel_name) if channel_name else context.channel
        
        if recheck:
            await channel.send("Checking raidlogs, back in a bit!")
            await self.monitor_clans(self.clans)

        since = datetime.strptime(since, "%Y-%m-%d") if since is not None else datetime.now() - timedelta(days=365)

        if limit is None:
            limit = len(self.clans) * 3
        elif limit == 0:
            limit = None

        Skills = Log.alias()
        
        skills_query = Skills.select(Skills.user_id,
                                     (fn.COUNT(Skills.id) + (fn.IFNULL(PriorActivity.skills, 0))).alias("skills"))\
                             .join_from(Skills, PriorActivity, JOIN.LEFT_OUTER, on=(Skills.user_id == PriorActivity.id))\
                             .join_from(Skills, Raid)\
                             .where(Skills.action == RaidAction.DreadMachineUse, Raid.start >= since, Raid.clan_name << [x[0] for x in self.clans])\
                             .group_by(Skills.user_id)\
                             .alias("sq")
        
        right_joined_skills_query = PriorActivity.select((PriorActivity.id).alias("user_id"), 
                                    (fn.IFNULL(PriorActivity.skills, skills_query.c.skills)).alias("skills"))\
                            .join_from(PriorActivity, skills_query, JOIN.LEFT_OUTER, on=(skills_query.c.user_id == PriorActivity.id))
        
        skills_query = skills_query | right_joined_skills_query #DIY FULL OUTER JOIN
        
        kills_query = Log.select(Log.user_id,
                                 Log.username.alias("Username"),
                                 (fn.SUM(Log.turns)+ (fn.IFNULL(PriorActivity.kills, 0))).alias("kills"))\
                         .join_from(Log, PriorActivity, JOIN.LEFT_OUTER, on=(Log.user_id == PriorActivity.id))\
                         .join_from(Log, Raid)\
                         .where(Log.action == RaidAction.Victory, Raid.name == "dreadsylvania", Raid.start >= since, Raid.clan_name in [x[0] for x in self.clans])\
                         .group_by(Log.user_id)

        rankings_query = Log.select(kills_query.c.username.alias("Username"),
                                            kills_query.c.kills.alias("Kills"),
                                            fn.IFNULL(skills_query.c.skills, 0).alias("Skills"),
                                            (kills_query.c.kills / (fn.IFNULL(skills_query.c.skills, 0) + 0.5)).alias("KillsPerSkill"))\
                                    .join_from(Log, skills_query, JOIN.LEFT_OUTER, on=(Log.user_id == skills_query.c.user_id))\
                                    .join_from(Log, kills_query, JOIN.LEFT_OUTER, on=(Log.user_id == kills_query.c.user_id))\
                                    .group_by(kills_query.c.user_id)\
                                    .order_by(SQL("KillsPerSkill").desc())\

        rankings = [x for x in [r for r in rankings_query.dicts()] if x["Username"] and not x["Username"].lower() in excluded_list]
        table = tabulate(rankings, headers="keys")
        table = table[:1900]
        message = "__SKILL RANKINGS__ \n```\n{}\n```".format(table)

        if channel_name:
            await context.send("Sending skills to {}".format(channel.name))
        if send_message:
            await channel.send(message)
        else:
            return message
            
    
    
    
    @commands.command(name="status")
    async def status(self, context, recheck = True, send_message = True, channel_name: str = None, description: str = None):
        await context.invoke(self.summary, recheck, send_message, channel_name, description)

    @commands.command(name="summary")
    async def summary(self, context, recheck = True, send_message = True, channel_name: str = None, description: str = None):
        """
        Post a summary of all the Dreadsylvania instances currently being monitored.

        :param channel_name: Channel to post the summary to. If not specified, the bot will respond
                             to you in a PM
        :param description: Text to appear inline with the summary.
        :return:
        """
        channel = (await self.get_channel(context, channel_name)) if channel_name else context.message.channel
        
        if recheck:
            await channel.send("Checking raidlogs, back in a bit!")
            await self.monitor_clans(self.clans)
        
        message = "__DREAD STATUS__\n"

        if description is not None:
            message += "{}\n\n".format(description)
        
        for raid in Raid.select().where(Raid.name == "dreadsylvania", Raid.end == None, Raid.clan_name << [x[0] for x in self.clans]):
            skip_clan = False
            for clan in excluded_clans:
                if raid.clan_id in clan:
                    skip_clan = True
            if skip_clan is True:     
                print("Skipping " + raid.clan_name)
                continue
            else:
                summary = json.loads(raid.summary)

                kills = {"forest": 1000, "village": 1000, "castle": 1000}

                for line in summary:
                    m = kills_pattern.match(line.replace(",",""))
                    if m:
                        kills[m.group(2).lower()] -= int(m.group(1))

                extra = None
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadMachineFix).exists():
                    machine_uses = Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadMachineUse).count()
                    left = 3 - machine_uses
                    extra = " ({} skill{} left)".format(left, "" if left == 1 else "s")
                else:
                    extra = " (needs capacitor)"

                message += "**{}**: {}/{}/{}{}\n".format(raid.clan_name, kills["forest"], kills["village"], kills["castle"], extra or "")
        message += "\n"

        if channel_name:
            await context.send("Sending summary to {}".format(channel.name))
        if send_message:
            await channel.send(message)
        else:
            return message

    @commands.command(name="clan")
    async def clan(self, context, clanname, recheck = True, send_message = True, channel_name: str = None):
        channel = (await self.get_channel(context, channel_name)) if channel_name else context.message.channel
        
        tocheck = None
        for clan in self.allclans:
            if clanname.lower() in clan[0].lower() or clanname.lower() in clan[2]:
                tocheck = clan
                break
        
        if recheck:
            await channel.send("Checking raidlogs, back in a bit!")
            await self.monitor_clans([tocheck])
        
        message = ""
        for raid in Raid.select().where(Raid.name == "dreadsylvania", Raid.end == None, Raid.clan_name == tocheck[0]):
            message = "__**STATUS UPDATE FOR {}**__ \n".format(tocheck[0].upper())
            summary = json.loads(raid.summary)

            kills = {"forest": 1000, "village": 1000, "castle": 1000}

            for line in summary:
                m = kills_pattern.match(line.replace(",", ""))
                if m:
                    kills[m.group(2).lower()] -= int(m.group(1))
            message += "{}/{}/{} kills remaining\n\n".format(kills["forest"], kills["village"], kills["castle"])
            message += "__FOREST__ \n"
            if kills["forest"]:
                if not Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadUnlock, Log.data == "{\"location\": \"attic of the cabin\"}").exists():
                    message += "**Cabin attic needs unlocking** \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadUnlock, Log.data == "{\"location\": \"fire watchtower\"}").exists():
                    message += "Watchtower open, you can grab freddies if you like \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadGotItem, Log.data == "{\"item\": \"Dreadsylvanian auditor's badge\"}").exists():
                    message += "~~Auditor's badge claimed~~ \n"
                else:
                    message += "Auditor's badge available (Cabin -> Basement -> Lockbox) \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadBanishElement, Log.data == "{\"element\": \"spooky\", \"location\": \"forest\"}").exists():
                    message += "~~Intricate music box parts claimed~~ \n"
                else:
                    message += "Intricate music box parts available (Cabin -> Attic -> Music Box as AT (also banishes spooky from forest)) \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadGotItem, Log.data == "{\"item\": \"blood kiwi\"}").exists():
                    message += "~~Blood kiwi claimed~~ \n"
                else:
                    message += "Blood kiwi available (Tree, Root Around -> Look Up + Climb -> Stomp) \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadGotItem, Log.data == "{\"item\": \"chunk of moon-amber\"}").exists():
                    message += "~~Moon-amber claimed~~ \n"
                else:
                    message += "Moon-amber available (Tree -> Climb -> Shiny Thing (requires muscle class)) \n"
            else:
                message += "~~Forest fully cleared~~ \n"
            
            message += "__VILLAGE__ \n"
            if kills["village"]:
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadUnlock, Log.data == "{\"location\": \"schoolhouse\"}").exists():
                    message += "Schoolhouse is open, go get your pencils! \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadUnlock, Log.data == "{\"location\": \"master suite\"}").exists():
                    message += "Master suite is open, grab some eau de mort? \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadHangee).exists():
                    message += "~~Hanging complete~~ \n"
                else:
                    message += "Hanging available (Square, Gallows -> Stand on Trap Door + Gallows -> Pull Lever) \n"
            else:
                message += "~~Village fully cleared~~ \n"
            
            message += "__CASTLE__ \n"
            if kills["castle"]:
                if not Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadUnlock, Log.data == "{\"location\": \"lab\"}").exists():
                    message += "**Lab needs unlocking** \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadMachineFix).exists():
                    machine_uses = Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadMachineUse).count()
                    left = 3 - machine_uses
                    if left:
                        message += "{} skill{} available.\n".format(left, "" if left == 1 else "s")
                    else:
                        message += "~~All skills claimed~~ \n"
                else:
                    message += "Machine needs repairing (with skull capacitor) \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadGotItem, Log.data == "{\"item\": \"roast beast\"}").exists():
                    message += "~~Dreadful roast claimed~~ \n"
                else:
                    message += "Dreadful roast available (Great Hall -> Dining Room -> Grab roast) \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadGotItem, Log.data == "{\"item\": \"wax banana\"}").exists():
                    message += "~~Wax banana claimed~~ \n"
                else:
                    message += "Wax banana available (Great Hall -> Dining Room -> Levitate (requires myst class) \n"
                if Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadGotItem, Log.data == "{\"item\": \"stinking agaric\"}").exists():
                    message += "~~Stinking agaricus claimed~~ \n"
                else:
                    message += "Stinking agaricus available (Dungeons -> Guard Room -> Break off bits) \n"
            else:
                message += "~~Castle fully cleared~~ \n"
                

        if channel_name:
            await context.send("Sending summary to {}".format(channel.name))
        if send_message:
            await channel.send(message)
        else:
            return message

    @commands.command(name="update")
    @team_only()
    async def update(self, context, channel_name: str = None, description: str = None):
        channel = (await self.get_channel(context, channel_name)) if channel_name else context.message.channel
        
        await channel.send("Checking raidlogs, back in a bit!")
        await self.monitor_clans(self.clans)
        
        message = "__**DREAD UPDATE FOR {}**__\n\n".format(datetime.now().strftime("%B %d, %Y").upper())
        message += "Hi " + get(context.guild.roles, id=532336645522063365).mention + "! Here is today's mostly-automated dreadsylvania update! \n"
        #message += "Hi " + "DUNGEON RUNNERS NO MENTION" + "! Here is today's mostly-automated dreadsylvania update! \n"
        message += "If you need any part of this summary, you can access updated skill rankings with !skill, and an updated status summary with !summary. \n"
        message += "Good luck, and happy hunting! \n\n"
        message += await context.invoke(self.summary, False, False)
        message += await context.invoke(self.skills, False, False)
        
        await channel.send(message)

    @commands.command(name="hod")
    async def hod(self, context, recheck = True, channel_name: str = None):
        channel = (await self.get_channel(context, channel_name)) if channel_name else context.message.channel
        
        await channel.send("Checking raidlogs, back in a bit!")
        await self.monitor_clans(self.allclans)
        
        message = ""
        for raid in Raid.select().where(Raid.name == "dreadsylvania", Raid.end == None, Raid.clan_name == "The Hogs of Destiny"):
            message = "__**HOD BANISH STATUS**__ \n"
            for location in ["forest", "village", "castle"]:
                for element in [("stinky", "stench"), ("spooky", "spooky"), ("sleazy", "sleaze"), ("hot", "hot"), ("cold", "cold")]:
                    data = "{{\"element\": \"{}\", \"location\": \"{}\"}}".format(element[0], location)
                    if not (location == "village" and element[1] in ["spooky", "stench"]):
                        if not Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadBanishElement, Log.data == data).exists():
                            message += "{} banish needed in {} {} \n".format(str(element[1]).capitalize(), str(location).capitalize(), banish_locations[(location, element[1])])
            village_banishes = [
                        Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadBanishElement, Log.data == "{\"element\": \"spooky\", \"location\": \"village\"}").exists(),
                        Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadBanishElement, Log.data == "{\"element\": \"stinky\", \"location\": \"village\"}").exists(),
                        Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadBanishType, Log.data == "{\"location\": \"village\", \"type\": \"ghosts\"}").count(),
                        Log.select().where(Log.raid == raid, Log.action == RaidAction.DreadBanishType, Log.data == "{\"location\": \"village\", \"type\": \"zombies\"}").count()
            ]
            if village_banishes[0]:
                if village_banishes[2] < 2:
                    message += "{} ghost banish{} still needed. \n".format("One" if village_banishes[2] else "Two", "" if village_banishes[2] else "es")
                
            elif village_banishes[1]:
                if village_banishes[3] < 2:
                    message += "{} zombie banish{} still needed. \n".format("One" if village_banishes[3] else "Two", "" if village_banishes[3] else "es")
            
            elif village_banishes[2]:
                message += "{} banish needed in {} {} \n".format("Spooky", "Village", banish_locations[("village", "spooky")])
                if village_banishes[3] < 2:
                    message += "One ghost banish still needed. \n"
            
            elif village_banishes[3]:
                message += "{} banish needed in {} {} \n".format("Stench", "Village", banish_locations[("village", "stench")])
                if village_banishes[3] < 2:
                    message += "One zombie banish still needed. \n"
            
            else:
                message += "Couldn't tell if this is a spooky ghost or a stench zombie instance. \n"
                message += "Either banish spooky {} or stench {} from the village. \n".format(banish_locations[("village", "spooky")], banish_locations[("village", "stench")])
            if message == "__**HOD BANISH STATUS**__ \n":
                message += "All banishes complete. \n"
            message += "(You may also want to run !clan hod)"
        if channel_name:
            await context.send("Sending summary to {}".format(channel.name))
        await channel.send(message)
