import peewee
from datetime import datetime, date

db = peewee.SqliteDatabase(None)

class Model(peewee.Model):
    class Meta:
        database = db


class User(Model):
    kol_id = peewee.IntegerField(primary_key=True)
    discord_id = peewee.IntegerField()
    token = peewee.TextField(null=True)


class Raid(Model):
    id = peewee.IntegerField(primary_key=True)
    name = peewee.TextField()
    clan_id = peewee.IntegerField()
    clan_name = peewee.TextField()
    summary = peewee.TextField(default="{}")
    start = peewee.DateField(default=date.today)
    end = peewee.DateField(null=True)


class Log(Model):
    raid = peewee.ForeignKeyField(Raid, backref="logs")
    category = peewee.TextField()
    username = peewee.TextField()
    user_id = peewee.IntegerField()
    action = peewee.TextField()
    data = peewee.TextField()
    turns = peewee.IntegerField(default=0)
    last_updated = peewee.DateTimeField(default=datetime.now)


class PriorActivity(Model):
    id = peewee.IntegerField()
    kills = peewee.IntegerField()
    skills = peewee.IntegerField()
