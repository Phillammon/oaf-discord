from discord.ext import commands
from libkol.Error import Error, UserNotFoundError
from uuid import uuid4

from util import pm_only
from db import User

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="associate")
    @pm_only()
    async def associate(self, context, kol_id = None):
        """ Member is asking to associate their Discord and KoL accounts """
        if kol_id is None:
            await context.send("Please specify your KoL id")
            return

        kol = self.bot.kol
        member = context.author
        token = str(uuid4())[:8]
        User.replace(kol_id=kol_id, discord_id=member.id, token=token).execute()
        try:
            await kol.kmail.send(recipient=kol_id, message="$verify {}".format(token))
            await context.send("Verification token sent to your account via kmail. Paste the command from there into this DM.")
        except UserNotFoundError:
            await context.send("User id is invalid")
        except Error as e:
            print(e)
            await context.send("There was an error sending you a kmail")

    @commands.command(name="verify")
    @pm_only()
    async def verify(self, context, token=None):
        """ Member is completing the verification process """
        if token is None:
            await context.send("You must specify a token")
            return

        member = context.author
        user = User.get_or_none(discord_id=member.id, token=token)
        if user is None:
            await context.send("That verification token is invalid.")
            return

        user.token = None
        user.save()
        await context.send("Verification complete")
