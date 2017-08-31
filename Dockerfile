FROM fcollman/render-python-client:master
MAINTAINER Forrest Collman (forrest.collman@gmail.com)

WORKDIR /share/render-modules
COPY . /share/render-modules
RUN pip install -e /share/render-modules

