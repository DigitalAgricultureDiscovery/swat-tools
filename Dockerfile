FROM python:3.9-bullseye

ENV PYTHONBUFFERED=1
ENV JAVA_HOME=/usr/lib/jvm/default-java

WORKDIR /app

RUN useradd -u 1000 nonroot

RUN apt-get update && apt-get install -y software-properties-common gdal-bin libgdal-dev default-jre

# Install Python dependencies
RUN python -m pip install --upgrade pip
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# Must install last to prevent an issue with reading raster data into 
# numpy arrays that occurs when installed at the same time as numpy
RUN pip install gdal==3.2.2.1

RUN mkdir /var/log/swat-tools

COPY ./app /app

# Copy UCanAccess
COPY UCanAccess-5.0.1.bin /opt/UCanAccess

USER nonroot