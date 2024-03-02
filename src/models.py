from peewee import *

db_password = os.environ["DB_PASSWORD"]
db_user = os.environ["DB_USER"]
db_host = os.environ["DB_HOST"]
database = PostgresqlDatabase('projects', **{'host': db_host, 'user': db_user, 'password': db_password})

class UnknownField(object):
    def __init__(self, *_, **__): pass

class BaseModel(Model):
    class Meta:
        database = database

class Challenges(BaseModel):
    bi_weeks = IntegerField(null=True)
    end = DateField()
    name = TextField()
    start = DateField()

    class Meta:
        table_name = 'challenges'

class ChallengeWeeks(BaseModel):
    bye_week = BooleanField(null=True)
    challenge = ForeignKeyField(column_name='challenge_id', field='id', model=Challenges, null=True)
    end = DateField(null=True)
    green = BooleanField(null=True)
    start = DateField(null=True)
    week_of_year = IntegerField(null=True)

    class Meta:
        table_name = 'challenge_weeks'

class Challengers(BaseModel):
    name = TextField()

    class Meta:
        table_name = 'challengers'

class ChallengerChallenges(BaseModel):
    challenge = ForeignKeyField(column_name='challenge_id', field='id', model=Challenges)
    challenger = ForeignKeyField(column_name='challenger_id', field='id', model=Challengers)
    knocked_out = BooleanField(constraints=[SQL("DEFAULT false")], null=True)

    class Meta:
        table_name = 'challenger_challenges'
        indexes = (
            (('challenger', 'challenge'), True),
        )
        primary_key = CompositeKey('challenge', 'challenger')

class Checkins(BaseModel):
    challenge_week = ForeignKeyField(column_name='challenge_week_id', field='id', model=ChallengeWeeks, null=True)
    day_of_week = TextField()
    id = IntegerField(constraints=[SQL("DEFAULT nextval('checkins_id_seq'::regclass)")])
    name = TextField()
    text = TextField(null=True)
    tier = TextField()
    time = DateTimeField()

    class Meta:
        table_name = 'checkins'
        indexes = (
            (('name'), True),
        )
        primary_key = CompositeKey('name', 'time')