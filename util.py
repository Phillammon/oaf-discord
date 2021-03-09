from discord.ext import commands

def pm_only():
    async def predicate(context):
        if context.guild is not None:
            raise commands.MissingPermissions("This command can only be issued via DM")
        return True
    return commands.check(predicate)

stoppers = [
    263438077865754644,
    104679335327178752,
    179048996327784448,
    145957353487990784,
    466602373679415307
]

def team_only(position = 13):
    async def predicate(context):
        if not context.author.id in stoppers:
            await context.channel.send("You do not have the required permissions to run that command.")
            raise commands.MissingPermissions("Not allowed to run this command")
        return True
    return commands.check(predicate)

