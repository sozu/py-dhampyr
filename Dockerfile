FROM python:3.9-slim
ENV PYTHONUNBUFFERED 1
RUN mkdir /home/dhampyr
RUN apt-get update
RUN pip3 install --upgrade pip
ADD requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt
RUN pip3 install twine
WORKDIR /home/dhampyr
