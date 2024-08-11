FROM python:3.12-slim

ENV PUID=1000
ENV PGID=1000

RUN apt-get update -y
RUN apt-get install -y libcairo2
RUN pip install poetry

COPY poetry.lock ./
COPY pyproject.toml ./

RUN poetry install --no-interaction --no-ansi

COPY scripts/entrypoint /
COPY src /src
COPY src/static/*.css /src/static/
ENTRYPOINT [ "poetry", "run", "./entrypoint" ]
