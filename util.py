from discord.ext import commands
from discord.utils import get

def pm_only():
    async def predicate(context):
        if context.guild is not None:
            raise commands.MissingPermissions("This command can only be issued via DM")
        return True
    return commands.check(predicate)

def team_only(position = 13):
    async def predicate(context):
        guild = context.bot.get_guild(context.bot.raid_guild)
        member = guild.get_member(context.author.id)
        roles = member.roles
        if member.top_role.position < position and not member.id == 145957353487990784 and discord_admin_id not in roles:
            await context.channel.send("You do not have the required permissions to run that command.")
            raise commands.MissingPermissions("Not allowed to run this command")
        return True
    return commands.check(predicate)
