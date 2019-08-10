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
 pip install -r requirements.txt &&\
 # there is a gotcha here, that em_stitch could possibly not work
 # with the render-modules opencv contrib version
 # had tried to fix in em_stitch setup.py
 # but pip install does not respect that somehow
 echo $(cat requirements.txt | grep opencv) > opencv_requirements.txt &&\
 pip uninstall -y opencv-python opencv-contrib-python &&\
 pip install -r opencv_requirements.txt &&\
 python setup.py install
ENTRYPOINT ["/bin/bash","/shared/render-modules/entrypoint.sh"]
