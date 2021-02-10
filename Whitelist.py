from tqdm import tqdm
from discord.ext import commands
from datetime import date

from util import team_only
from DiscordIO import DiscordIO
from db import User

class Whitelist(commands.Cog):
    def __init__(self, bot, clans=[]):
        self.bot = bot
        self.clans = clans

    @team_only()
    @commands.command(name="whitelist")
    async def whitelist(self, context, player = None):
        """ Add member to clan whitelists """
        mentions = context.message.mentions
        kol = self.bot.kol

        if len(mentions) > 0:
            member = mentions[0]
            user = User.get_or_none(User.discord_id == member.id, User.token.is_null())
            if user is None:
                await context.send("That user has not attached their KoL account.")
                return
            player = user.kol_id

        if player is None:
            await context.send("Please specify a KoL id, name or a mention a Discord user")
            return

        message = await context.send("Adding user to clans")
        message_stream = DiscordIO(message)
        result = "Whitelisting complete\n"
        with tqdm(self.clans, desc="Adding user to clans", file=message_stream, bar_format="{l_bar}`{bar}`|") as p:
            for clan_name, clan_id, clan_aliases in p:
                success = await kol.join_clan(id=clan_id)
                if success is False:
                    result += "* Joining *{}* failed\n".format(clan_name)
                    continue

                ranks = await kol.clan.get_ranks()
                rank = next((r for r in ranks if r["name"].lower() == "dungeon runner"), None)

                if rank is None:
                    result += "* No role matching *Dungeon Runner* found in *{}*\n".format(clan_name)
                    continue

                success = await kol.clan.add_user_to_whitelist(player, rank=rank["id"], title="Added by ASSistant ({})".format(date.today()))
                if success is False:
                    result += "* Whitelisting to *{}* failed\n".format(clan_name)

        message_stream.print(result)
