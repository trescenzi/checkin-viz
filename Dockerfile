FROM python:3.11-slim-bullseye

ENV PUID=1000
ENV PGID=1000

RUN apt-get update -y
RUN apt-get install -y libcairo2
RUN pip install pipenv

COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --ignore-pipfile --system

COPY scripts/entrypoint /
COPY src /src
RUN chmod 777 /src/static
# RUN chmod +x entrypoint.sh
ENTRYPOINT [ "./entrypoint" ]
