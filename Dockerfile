FROM fcollman/render-python-client:master
MAINTAINER Forrest Collman (forrest.collman@gmail.com)

WORKDIR /shared/render-modules
COPY . /shared/render-modules
RUN apt-get update && apt-get install -y libxcomposite-dev gcc && rm -rf /var/lib/apt/lists/*
SHELL ["/bin/bash", "-c"]
RUN conda create -n render-modules --clone root && source activate render-modules && conda install -y -c conda-forge rtree 
RUN source activate render-modules &&\
 conda install -y pip &&\
 conda install -y -c conda-forge fast-histogram &&\
 pip uninstall -y opencv-python opencv-contrib-python &&\
 # em_stitch tries not to clobber existing installs of
 # opencv or opencv_contrib, but, the way, in its setup.py
 # assumes that something is already installed, not just also
 # listed in the requirements.txt
 # so, install opencv first, then everything else and em_stitch
 # will try to respect it
 echo $(cat requirements.txt | grep opencv) > opencv_requirements.txt &&\
 pip install -r opencv_requirements.txt &&\
 pip install -no-binary em_stitch -r requirements.txt &&\
 python setup.py install
ENTRYPOINT ["/bin/bash","/shared/render-modules/entrypoint.sh"]
