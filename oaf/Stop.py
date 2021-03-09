from discord.ext import commands
from util import pm_only, team_only

class Stop(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @team_only()
    @commands.command(name="stop")
    async def stop(self, context):
        """ Brings down bot for maintainance """
        await context.channel.send("Beep boop, dying.")
        await self.bot.logout()
