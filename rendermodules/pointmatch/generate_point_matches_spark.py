import json
import os
import subprocess
from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
import renderapi
from rendermodules.module.render_module import RenderModule, RenderModuleException
from rendermodules.pointmatch.schemas import PointMatchClientParametersSpark

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.pointmatch.generate_point_matches_spark"

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "sparkhome": "/allen/programs/celltypes/workgroups/em-connectomics/ImageProcessing/utils/spark/",
    "masterUrl":"spark://10.128.124.100:7077",
    "logdir": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/sparkLogs/",
    "jarfile": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-spark-client/target/render-ws-spark-client-0.3.0-SNAPSHOT-standalone.jar",
    "className":"org.janelia.render.client.spark.SIFTPointMatchClient",
    "baseDataUrl":"http://em-131fs:8080/render-ws/v1",
    "owner": "gayathri_MM2",
    "collection": "mm2_rough_align_test",
    "pairJson": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/rough/tilePairs/tile_pairs_mm2_montage_scape_test_z_1015_to_1035_dist_5.json",
    "SIFTfdSize": 8,
    "SIFTsteps": 3,
    "matchMaxEpsilon": 20.0,
    "maxFeatureCacheGb": 15,
    "SIFTminScale": 0.38,
    "SIFTmaxScale": 0.82,
    "renderScale": 0.3,
    "matchRod": 0.9,
    "matchMinInlierRatio": 0.0,
    "matchMinNumInliers": 8,
    "matchMaxNumInliers": 200
}
def form_sift_params(args):
    sift_params = " --SIFTfdSize {}".format(args['SIFTfdSize'])
    sift_params += " --SIFTsteps {}".format(args['SIFTsteps'])
    sift_params += " --matchMaxEpsilon {}".format(args['matchMaxEpsilon'])
    sift_params += " --maxFeatureCacheGb {}".format(args['maxFeatureCacheGb'])
    sift_params += " --SIFTminScale {}".format(args['SIFTminScale'])
    sift_params += " --SIFTmaxScale {}".format(args['SIFTmaxScale'])
    sift_params += " --renderScale {}".format(args['renderScale'])
    sift_params += " --matchRod {}".format(args['matchRod'])
    sift_params += " --matchMinInlierRatio {}".format(args['matchMinInlierRatio'])
    sift_params += " --matchMinNumInliers {}".format(args['matchMinNumInliers'])
    sift_params += " --matchMaxNumInliers {}".format(args['matchMaxNumInliers'])
    clipWidth = args.get('clipWidth',None)
    clipHeight = args.get('clipHeight',None)
    if clipWidth is not None:
        sift_params += " --clipWidth {}".format(clipWidth)
    if clipHeight is not None:
        sift_params += " --clipHeight {}".format(clipHeight)
    return sift_params

class PointMatchClientModuleSpark(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = PointMatchClientParametersSpark
        super(PointMatchClientModuleSpark, self).__init__(
            schema_type=schema_type, *args, **kwargs)

    def run(self):
        # prepare sift parameters     
        sift_params = form_sift_params(self.args)

        sparksubmit = os.path.join(self.args['sparkhome'], 'bin', 'spark-submit')

        # prepare the spark submit command
        cmd = "{} --master {}".format(sparksubmit, self.args['masterUrl'])
        cmd = cmd + " --executor-memory {}".format(self.args['memory'])
        cmd = cmd + " --driver-memory {}".format(self.args['driverMemory'])
        cmd = cmd + " --class {} {}".format(self.args['className'], self.args['jarfile'])
        cmd = cmd + " --baseDataUrl {}".format(self.args['baseDataUrl'])
        cmd = cmd + " --owner {}".format(self.args['owner'])
        cmd = cmd + " --collection {}".format(self.args['collection'])
        cmd = cmd + " --pairJson {}".format(self.args['pairJson'])

        cmd_to_submit = cmd + sift_params

        ret=os.system(cmd_to_submit)
        if ret != 0:
            raise RenderModuleException("PointMatchClientModuleSpark failed with inputs {} ",self.args)
        
        mc=renderapi.pointmatch.get_matchcollections(self.args['owner'],render=self.render)
        collection = next(m for m in mc if m['collectionId']['name']==self.args['collection'])
        self.output(collection)

if __name__ == "__main__":
    module = PointMatchClientModuleSpark(input_data=example)
    #module = PointMatchClientModuleSpark(schema_type=PointMatchClientParameters)
    module.run()
