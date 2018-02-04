FROM fcollman/render-python-client:master

WORKDIR /shared/render-modules
COPY . /shared/render-modules
RUN conda update conda && conda install -y -c conda-forge rtree 
RUN apt-get update && apt-get install -y libxcomposite-dev && rm -rf /var/lib/apt/lists/*
RUN python setup.py install

