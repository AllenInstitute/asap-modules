conda create --name render-modules --prefix $IMAGE_PROCESSING_DEPLOY_PATH python=2.7
source activate render-modules 
pip install -r ../requirements.txt
