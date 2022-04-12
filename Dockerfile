FROM python:3.9-bullseye

ENV PYTHONBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y software-properties-common gdal-bin libgdal-dev

COPY ./requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt


COPY ./code /app
