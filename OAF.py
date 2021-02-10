from discord.ext import commands
import discord
from util import team_only
import requests
import re
import string
import pickle
import os
import html.parser
import urllib.parse
from libkol import Session, Item
import asyncio
import datetime
from dotenv import load_dotenv
import os
import random

load_dotenv()

decapitalize = lambda s: s[:1].lower() + s[1:] if s else ''
brackets_pattern = re.compile('\[\[[^\]]*\]\]')

outcomes = ["It is certain.",
"It is decidedly so.",
"Without a doubt.",
"Yes - definitely.",
"You may rely on it.",
"As I see it, yes.",
"Most likely.",
"Outlook good.",
"Yes.",
"Signs point to yes.",
"Reply hazy, try again.",
"Ask again later.",
"Better not tell you now.",
"Cannot predict now.",
"Concentrate and ask again.",
"Don't count on it.",
"My reply is no.",
"My sources say no.",
"Outlook not so good.",
"Very doubtful.",
"If CDM has a free moment, sure.",
"Why not?",
"How am I meant to know?",
"I guess???",
"...you realise that this is just a random choice from a list of strings, right?",
"I have literally no way to tell.",
"Ping Bobson, he probably knows",
"Check the wiki, answer's probably in there somewhere.",
"The wiki has the answer.",
"The wiki has the answer, but it's wrong.",
"I've not finished spading the answer to that question yet.",
"The devs know, go pester them instead of me.",
"INSUFFICIENT DATA FOR MEANINGFUL ANSWER",
"THERE IS AS YET INSUFFICIENT DATA FOR A MEANINGFUL ANSWER"]

class CanonicalFinder(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.canon_url = ""
    def feed(self, data, url = ""):
        self.canon_url = url
        super().feed(data)
        return self.canon_url
    def handle_starttag(self, tag, attrs):
        if tag == "link":
            if attrs[0][1] == "canonical":
                self.canon_url = "http://kol.coldfront.net" + attrs[1][1]

class IOTMFinder(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.month = ""
        self.desc = ""
        self.iotm = ""
        self.image_url = ""
    def feed(self, data):
        super().feed(data)
        return self.iotm, self.image_url, self.desc, self.month
    def handle_data(self, data):
        if len(data.strip()):
            if not self.desc and not ("The Kingdom of Loathing" == data)and not ("An Adventurer" in data) :
                if not self.month:
                    self.month = data
                elif not self.iotm:
                    self.iotm = data
                else:
                    self.desc = data
                
    def handle_starttag(self, tag, attrs):
        if tag == "img":
            if not self.image_url and not any("swordguy" in url for url in [x[1] for x in attrs]) and not any("getitnow" in url for url in [x[1] for x in attrs]):
                self.image_url = [x[1] for x in attrs if x[0] == "src"][0]

class OAF(commands.Cog):
    def __init__(self, bot, cache = {}):
        self.bot = bot
        self.finder = CanonicalFinder()
        self.cache = cache
    
    @commands.Cog.listener()
    async def on_message(self, message):
        brackets = brackets_pattern.findall(message.content)
        for invocation in brackets:
            item = invocation[2:-2]
            msg = ""
            embed = ""
            if item[0] == "!":
                msg, embed = await self.wiki_link(item[1:], True)
            elif item[0] == "$":
                msg, embed = await self.mall_price(item[1:], False)
            else:
                msg, embed = await self.wiki_link(item)
            await message.channel.send(msg, embed = embed)
        if "good bot" in message.content.lower():
            await message.channel.send("<3")
        elif "bad bot" in message.content.lower():
            await message.channel.send("<:rude2:585646615390584844><:rude3:585646615403167745>")

    async def mall_price(self, item, ignore_cache = False):
        await self.bot.kol.login(os.getenv("KOL_USER"), os.getenv("KOL_PASS"))
        name, cachetime = self.find_name(item, ignore_cache)
        msg = ""
        embed = None
        if name == "noitem":
            msg = "You'll need to give me more than that."
        elif name == "googlestumped":
            msg = "I have no idea what you're talking about."
        elif name == "quotareached":
            msg = "I couldn't find that on the wiki, and I appear to have used my google search quota for the day. Try to be more precise, or try again tomorrow."
        else:
            embed = discord.Embed(url = "http://kol.coldfront.net/thekolwiki/index.php/" + urllib.parse.quote(name.replace(" ", "_")), title = name)
            item = None
            try:
                item = await Item[name]
            except:
                try:
                    item = await Item[decapitalize(name)]
                except:
                    pass
            if item:
                unlimited = await item.get_mall_price()
                limited = await item.get_mall_price(True)
                if unlimited:
                    embed.description = "{:,} meat \n".format(unlimited)
                    if limited and limited < unlimited:
                        embed.description += "(or {:,} meat limited per day)".format(limited)
                else:
                    embed.description = name + " wasn't found in the mall."
                embed.set_thumbnail(url = "http://images.kingdomofloathing.com/itemimages/" + item.image)
            embed.set_footer(icon_url = "http://images.kingdomofloathing.com/itemimages/oaf.gif", text="Fetched " + cachetime + ". Problems? Message madowl#0828 on discord.")
        return msg, embed

    async def wiki_link(self, item, ignore_cache = False):
        name, cachetime = self.find_name(item, ignore_cache)
        msg = ""
        embed = None
        if name == "noitem":
            msg = "You'll need to give me more than that."
        elif name == "googlestumped":
            msg = "I have no idea what you're talking about."
        elif name == "quotareached":
            msg = "I couldn't find that on the wiki, and I appear to have used my google search quota for the day. Try to be more precise, or try again tomorrow."
        else:
            embed = discord.Embed(url = "http://kol.coldfront.net/thekolwiki/index.php/" + urllib.parse.quote(name.replace(" ", "_")), title = name)
            item = None
            try:
                item = await Item[name]
            except:
                try:
                    item = await Item[decapitalize(name)]
                except:
                    pass
            if item:
                embed.description = await self.get_item_description(item)
                embed.set_thumbnail(url = "http://images.kingdomofloathing.com/itemimages/" + item.image)
            embed.set_footer(icon_url = "http://images.kingdomofloathing.com/itemimages/oaf.gif", text="Fetched " + cachetime + ". Problems? Message madowl#0828 on discord.")
        return msg, embed
    
    async def get_item_description(self, item):
        output = ""
        if item.type == "other":
            if item.food or item.booze or item.spleen:
                avgstring = ""
                if item.food:
                    output += "Food (size " + str(item.fullness) + ", "
                    if item.fullness:
                        avgstring = "(~{0:.1f} adventures per fullness) \n".format((item.gained_adventures_min + item.gained_adventures_max)/(2*item.fullness))
                elif item.booze:
                    output += "Booze (potency " + str(item.inebriety) + ", "
                    if item.inebriety:
                        avgstring = "(~{0:.1f} adventures per inebriety) \n".format((item.gained_adventures_min + item.gained_adventures_max)/(2*item.inebriety))
                elif item.spleen:
                    output += "Spleen (toxicity " + str(item.spleenhit) + ", "
                    if item.spleen:
                        avgstring = "(~{0:.1f} adventures per spleen) \n".format((item.gained_adventures_min + item.gained_adventures_max)/(2*item.spleenhit))
                output += (item.quality if item.quality else "???") + ")"
                if item.level_required:
                    output += ", level " + str(item.level_required) + " required. \n"
                    if item.level_required > 12:
                        output += " (Can't be consumed in ronin or hardcore) \n"
                else:
                    output += ", no level requirement. \n"
        else:
            if item.type == "weapon":
                output += item.type.capitalize() 
                output += " (" + str(item.weapon_hands) + "-handed" + item.weapon_type + "), " 
                output += str(int(item.power*0.1)) + " to " + str(int(item.power*0.2)) + " damage"
            else:
                output += item.type.capitalize().replace("_", " ") + ("" if not item.power else ", power " + str(item.power))
            if item.required_muscle:
                output += ", " + str(item.required_muscle) + " muscle required. \n"
            elif item.required_moxie:
                output += ", " + str(item.required_moxie) + " moxie required. \n"
            elif item.required_mysticality:
                output += ", " + str(item.required_mysticality) + " mysticality required. \n"
            else:
                output += ", no stat requirements. \n"
        if not item.tradeable or not item.discardable:
            if not item.tradeable:
                output += "Can't be traded"
                if not item.discardable:
                    output += " or discarded"
                output += "."
            else:
                output += "Can't be discarded."
            output += " \n"
        if item.quest:
            output += "Quest Item \n"
        if not item.type == "other":
            await self.bot.kol.login(os.getenv("KOL_USER"), os.getenv("KOL_PASS"))
            desc = await item.get_description()
            for line in desc["enchantments"]:
                output += line + " \n"
        else:
            if item.food or item.booze or item.spleen:
                output += str(item.gained_adventures_min) + " to " + str(item.gained_adventures_max) + " adventures gained " + avgstring 
        return output
        
    def get_name_from_url(self, url):
        return urllib.parse.unquote("/".join(url.split("/")[5:])).replace("_", " ")

    def find_name(self, item, ignore_cache = False):
        print("Searching wiki for " + item)
        page_to_fetch = item.replace(" ", "_")
        crushed_name = (''.join(e for e in item if e.isalnum())).lower()
        now = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
        if ignore_cache:
            print("Cache override detected")
        else:
            if crushed_name in self.cache.keys():
                print(item + " found in cache")
                return self.cache[crushed_name]
        if not len(page_to_fetch):
            self.cache[crushed_name] = ("noitem", now)
            return self.cache[crushed_name]
        search = page_to_fetch.replace("-", "+")
        url = "http://kol.coldfront.net/thekolwiki/index.php?search={0}".format(search)
        r = requests.get(url=url, params = {})
        if not "noarticletext" in r.text and not "Bad Title" in r.text and not "kol.coldfront.net/thekolwiki/index.php?search=" in r.url:
            print(item + " found in wiki")
            url = self.finder.feed(r.text, r.url)
            self.cache[crushed_name] = (self.get_name_from_url(url), now)
            return self.cache[crushed_name]
        r = requests.get(url = "https://www.googleapis.com/customsearch/v1", params = {
            "key": os.getenv("GOOGLE_API_KEY"),
            "cx": os.getenv("CUSTOM_SEARCH"),
            "q": search.replace(" ", "-")
        })
        if r.status_code != 200:
            print("Got status code" + str(r.status_code) + " from google, failing")
            return "quotareached", None
        jsonresp = r.json()
        if "items" in jsonresp.keys():
            print(item + " found by google search")
            #print("Options:")
            #print([x["link"] for x in jsonresp["items"]])
            self.cache[crushed_name] = (self.get_name_from_url(jsonresp["items"][0]["link"]), now)
            return self.cache[crushed_name]
        print(item + " stumped google, failing.")
        self.cache[crushed_name] = ("googlestumped", now)
        return self.cache[crushed_name]

    @commands.command(name="iotm")
    async def iotm(self, context):
        extra = context.message.content[6:]
        url = "http://dev.kingdomofloathing.com/iotm.php" + (("?date=" + extra) if len(extra) else "")
        r = requests.get(url=url, params = {})
        name, image, desc, month = IOTMFinder().feed(r.text)
        embed = discord.Embed(url = url, title = month + ": " + name.capitalize() + "!")
        embed.set_thumbnail(url = image)
        embed.description = desc
        await context.message.channel.send(embed = embed)

    @commands.command(name="oops")
    async def oops(self, context):
        async for message in context.channel.history(limit=20):
            if message.author == self.bot.user:
                await message.delete()
                break

    @commands.command(name="8ball")
    async def oops(self, context):
        await context.message.channel.send(random.choice(outcomes))

    @commands.command(name="roll")
    async def roll(self, context):
        print("Rolling Dice")
        try:
            args = context.message.content[6:].split("d")
            if int(args[0]) > 100:
                print("Request too large.  Returning error.")
                await context.message.channel.send("The number of dice you tried to roll is greater than 100. Try 100 or less.")
            elif int(args[1]) > 1000000:
                print("Request too large.  Returning error.")
                await context.message.channel.send("The size of dice you tried to roll is greater than 1000000. Try 1000000 or less.")
            else:
                print("Trying to roll a %s" % args)
                count = 0
                for i in range(int(args[0])):
                    count += 1 + random.randrange(int(args[1]))
                    #print(count)
                await context.message.channel.send("Rolled {} on {}d{}.".format(count, args[0], args[1]))
        except Exception as e:
            await context.message.channel.send("Something about that didn't work. Don't feed me garbage.")
            
            
