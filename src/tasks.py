from huey import crontab, FileHuey
from main import determine_if_green
import logging

huey = FileHuey(path="./huey.txt")


@huey.task()
def example_task(n):
    print("-- RUNNING EXAMPLE TASK: CALLED WITH n=%s --" % n)
    return n


@huey.periodic_task(crontab(day_of_week="1", hour="6"))
def is_green_week():
    logging.debug("Checking if green")
    determine_if_green()
