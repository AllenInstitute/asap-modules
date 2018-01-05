import json
import os
import subprocess
from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
import renderapi
from rendermodules.module.render_module import RenderModule, RenderModuleException
from rendermodules.pointmatch.schemas import PointMatchClientParametersSpark,PointMatchClientOutputSchema

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
def add_arg(l,argname,args):
    value = args.get(argname,None)
    if value is not None:
        l+=["--{}".format(argname),args[argname]]

def form_sift_params_list(args):
    sift_params = []

    add_arg(sift_params,'SIFTfdSize',args)
    add_arg(sift_params,'SIFTsteps',args)
    add_arg(sift_params,'matchMaxEpsilon',args)
    add_arg(sift_params,'maxFeatureCacheGb',args)
    add_arg(sift_params,'SIFTminScale',args)
    add_arg(sift_params,'SIFTmaxScale',args)
    add_arg(sift_params,'renderScale',args)
    add_arg(sift_params,'matchRod',args)
    add_arg(sift_params,'matchMinInlierRatio',args)
    add_arg(sift_params,'matchMinNumInliers',args)
    add_arg(sift_params,'matchMaxNumInliers',args)
    add_arg(sift_params,'clipWidth',args)
    add_arg(sift_params,'clipHeight',args)
    return sift_params

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
    default_output_schema = PointMatchClientOutputSchema
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = PointMatchClientParametersSpark
        super(PointMatchClientModuleSpark, self).__init__(
            schema_type=schema_type, *args, **kwargs)

    def run(self):
        # prepare sift parameters     
        sift_params = form_sift_params_list(self.args)

        sparksubmit = os.path.join(self.args['sparkhome'], 'bin', 'spark-submit')

        # prepare the spark submit command
        cmd = [sparksubmit,"--master", self.args['masterUrl']]
        cmd += ["--executor-memory",self.args['memory']]
        cmd += ["--driver-memory",self.args['driverMemory']]
        if self.args.get('spark_files',None) is not None:
            for spark_file in self.args['spark_files']:
                cmd += ["--files",spark_file]
        if self.args.get('spark_conf',None) is not None:       
            for key,value in  self.args['spark_conf'].items():
                cmd+= ["--conf","{}='{}'".format(key,value)]
        cmd += ["--class",self.args['className'],self.args['jarfile']]
        add_arg(cmd,'baseDataUrl',self.args)
        add_arg(cmd,'owner',self.args)
        add_arg(cmd,'collection',self.args)
        add_arg(cmd,'pairJson',self.args)
 
        cmd_to_submit = cmd + sift_params

        try:
            subprocess.check_call(cmd_to_submit)
        except subprocess.CalledProcessError as e:
            raise RenderModuleException("PointMatchClientModuleSpark failed with inputs {} ",self.args)
        
        mc=renderapi.pointmatch.get_matchcollections(self.args['owner'],render=self.render)
        collection = next(m for m in mc if m['collectionId']['name']==self.args['collection'])
        self.output(collection)

if __name__ == "__main__":
    module = PointMatchClientModuleSpark(input_data=example)
    #module = PointMatchClientModuleSpark(schema_type=PointMatchClientParameters)
    module.run()
