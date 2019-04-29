FROM python:3.7-stretch
ENV PYTHONUNBUFFERED 1
RUN mkdir /home/dhampyr
RUN apt-get update
RUN pip3 install --upgrade pip
ADD requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt
WORKDIR /home/dhampyr
