FROM fcollman/render-python-client:master
MAINTAINER Forrest Collman (forrest.collman@gmail.com)

WORKDIR /shared/render-modules
COPY . /shared/render-modules
RUN python setup.py install

