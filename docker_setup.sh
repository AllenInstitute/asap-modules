#docker pull atbigdawg:5000/fcollman/render-python-apps:reorg
#docker tag atbigdawg:5000/fcollman/render-python-apps:reorg fcollman/render-python-apps
docker build -t sharmishtaas/render_modules .
#docker tag sharmishtaas/luigi-scripts atbigdawg:5000/sharmishtaas/luigi-scripts
#docker push atbigdawg:5000/sharmishtaas/luigi-scripts
docker kill rm_container
docker rm rm_container
docker run -d --name rm_container \
-v /nas:/nas \
-v /nas2:/nas2 \
-v /nas3:/nas3 \
-v /nas4:/nas4 \
-v /data:/data \
-v /pipeline:/pipeline \
-v /etc/hosts:/etc/hosts \
-i -t sharmishtaas/render_modules

