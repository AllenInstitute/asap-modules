conda create --name asap --prefix $IMAGE_PROCESSING_DEPLOY_PATH python=3.11
source activate asap
pip install -r ../requirements.txt
