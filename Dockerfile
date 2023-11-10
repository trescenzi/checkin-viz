FROM python:3.11-slim-bullseye

ENV PUID=1000
ENV PGID=1000

RUN pip install pipenv

COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --ignore-pipfile --system

COPY scripts/entrypoint /
COPY src /src
# RUN chmod +x entrypoint.sh
ENTRYPOINT [ "./entrypoint" ]
