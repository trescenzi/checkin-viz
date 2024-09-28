from huey import crontab, FileHuey
from main import determine_if_green

huey = FileHuey(path="./huey_tasks")


@huey.task()
def example_task(n):
    print("-- RUNNING EXAMPLE TASK: CALLED WITH n=%s --" % n)
    return n


@huey.periodic_task(crontab(day_of_week="*", hour="6", minute="0"))
def is_green_week():
    print("Determining if green")
    determine_if_green()
