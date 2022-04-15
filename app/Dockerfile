# base image for container
FROM python:3.9-bullseye

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONBUFFERED=1
ENV JAVA_HOME=/usr/lib/jvm/default-java

# set working directory
WORKDIR /usr/src/app

# install system dependencies
RUN apt-get update && apt-get install -y software-properties-common gdal-bin libgdal-dev default-jre

# install python dependencies
RUN python -m pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# must install last to prevent an issue with reading raster data into 
# numpy arrays that occurs when installed at the same time as numpy
RUN pip install gdal==3.2.2.1

# create directory for app logs
RUN mkdir /var/log/swat-tools

# copy entrypoint.sh
COPY ./entrypoint.sh .
RUN sed -i 's/\r$//g' /usr/src/app/entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh

# copy application to /app directory
COPY . .

# copy UCanAccess
COPY ./UCanAccess-5.0.1.bin /opt/UCanAccess
