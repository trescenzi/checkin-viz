import os
import logging
import psycopg

connection_string = os.environ["DB_CONNECT_STRING"]

class Checkin:
    """
    name |time| tier | day_of_week |text| challenge_week_id |  id
    """
    def __init__(self, name=None, time=None, tier=None, day_of_week=None, text=None, challenge_week_id=None, id=None):
        if None not in (name, time, tier, day_of_week, text, challenge_week_id, id):
            self.name = name
            self.time = time
            self.tier = tier
            self.day_of_week = day_of_week
            self.text = text
            self.challenge_week_id = challenge_week_id
            self.id = id
        else:
            logging.info("name, time, tier, day_of_week, text, challenge_week_id, and id must be provided")

    def __str__(self):
        return "Checkin {id}: {name} {time} {tier} {day_of_week} {text}".format(id=self.id, name=self.name, time=self.time, tier=self.tier, day_of_week=self.day_of_week, text=self.text)

    @staticmethod
    def find_where(selector):
        with psycopg.connect(conninfo=connection_string) as conn:
            with conn.cursor() as cur:
                sql = "select c.name, c.time, c.tier, c.day_of_week, c.text, c.challenge_week_id, c.id from checkins c where " + selector;
                logging.info(sql)
                cur.execute(sql)
                return cur.fetchall()

    @staticmethod
    def find_by_week(week_id):
        checkins = Checkin.find_where("c.challenge_week_id = %s order by c.time" % week_id)
        return [Checkin(*c) for c in checkins]
        

class Challenge:
    def __init__(self, id=None, name=None, start=None, end=None):
        if None not in (id, name, start, end):
            self.id = id
            self.name = name
            self.start = start
            self.end = end
        else:
            logging.info("id, name, start, and end must be provided")
    def __str__(self):
        return "Challenge {id}: {name} {start}-{end}".format(id=self.id, name=self.name, start=self.start, end=self.end)

class Week:
    """Defines a week which has checkins and a challenge"""

    def __init__(
            self, 
            id=None, 
            start=None, 
            end=None, 
            week_of_year=None,
            challenge_id=None,
            green=None,
            bye_week=None,
            challenge=None,
            challenge_week=None,
            year=None,
        ):
        week = None
        if (id):
           week = Week.find_where_id_equals(id) 
        elif (start):
            week = Week.find_where_start_equals(start)
        elif (end):
            week = Week.find_where_end_equals(end)
        elif (week_of_year):
            week = Week.find_where_week_of_year_equals(week_of_year, year)
        elif (challenge_id):
            week = Week.find_where_challenge_id_equals(challenge_id, challenge_week)
        logging.info(week)
        self.start = week[0]
        self.end = week[1]
        self.id = week[2]
        self.challenge_id = week[3]
        self.week_of_year = week[4]
        self.green = week[5]
        self.bye_week = week[6]
        self._checkins = None
        challenge = Challenge(week[7], week[8], week[9], week[10])
        self.challenge = challenge

    def __str__(self):
        return "Week {id}: {start}-{end}; {week} of the year. Green: {green}, Bye: {bye_week}. {challenge}".format(start=self.start, end=self.end, id=self.id, week=self.week_of_year, green=self.green, bye_week=self.bye_week, challenge=self.challenge)

    @property
    def checkins(self):
        if self._checkins is None:
            self._checkins = Checkin.find_by_week(self.id)
        return self._checkins

    @staticmethod
    def find_where(selector):
        with psycopg.connect(conninfo=connection_string) as conn:
            with conn.cursor() as cur:
                sql = "select cw.start, cw.end, cw.id, cw.challenge_id, cw.week_of_year, cw.green, cw.bye_week, c.id, c.name, c.start, c.end from challenge_weeks cw join challenges c on c.id = cw.challenge_id where " + selector;
                logging.info(sql)
                cur.execute(sql)
                return cur.fetchone()

    @staticmethod
    def find_where_id_equals(id):
        return Week.find_where("id = %s" % id)

    @staticmethod
    def find_where_start_equals(start):
        return Week.find_where("start = %s" % start)

    @staticmethod
    def find_where_end_equals(end):
        return Week.find_where("\"end\" = %s" % end)

    @staticmethod
    def find_where_challenge_id_equals(challenge_id, challenge_week):
        weeks = Week.find_where("challenge_id = %s" % challenge_id)
        return weeks[challenge_week - 1]

    @staticmethod
    def find_where_end_equals(end):
        return Week.find_where("\"end\" = %s" % end)

    @staticmethod
    def find_where_week_of_year_equals(week_of_year, year=None):
        q = "week_of_year = %s" % week_of_year
        q = q if year is None else q + " and DATE_PART('year', cw.start) = '%s'" % year
        return Week.find_where(q)
