FROM fcollman/render-python:latest
MAINTAINER Forrest Collman (forrest.collman@gmail.com)


RUN mkdir -p /usr/local/render-modules
WORKDIR /usr/local/render-modules

COPY requirements.txt /usr/local/render-modules
RUN pip install -r requirements.txt
RUN pip install setuptools --upgrade --disable-pip-version-check
RUN pip install argschema --upgrade --disable-pip-version-check
RUN pip install jupyter
COPY . /usr/local/render-modules

