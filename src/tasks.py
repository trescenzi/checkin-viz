from huey import crontab, SqliteHuey
from green import determine_if_green

huey = SqliteHuey()


@huey.task()
def example_task(n):
    print("-- RUNNING EXAMPLE TASK: CALLED WITH n=%s --" % n)
    return n


@huey.periodic_task(crontab(hour="6", day="1"))
def is_green_week():
    print("Determining if green")
    determine_if_green()
