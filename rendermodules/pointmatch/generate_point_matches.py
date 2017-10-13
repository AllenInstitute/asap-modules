
import json
import os
import subprocess
from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
import renderapi
from ..module.render_module import RenderModule
from rendermodules.pointmatch.schemas import PointMatchClientParameters

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.pointmatch.generate_point_matches"


example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8998,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "method":"qsub",
    "no_nodes": 30,
    "ppn": 30,
    "queue_name": "emconnectome",
    "sparkhome": "/allen/programs/celltypes/workgroups/em-connectomics/ImageProcessing/utils/spark/",
    "pbs_template":"/allen/aibs/pipeline/image_processing/volume_assembly/utils/code/spark-submit/spinup_spark.pbs",
    "logdir": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/sparkLogs/",
    "jarfile": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-spark-client/target/render-ws-spark-client-0.3.0-SNAPSHOT-standalone.jar",
    "className":"org.janelia.render.client.spark.SIFTPointMatchClient",
    "baseDataUrl":"http://em-131fs:8998/render-ws/v1",
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


class PointMatchClientModule(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = PointMatchClientParameters
        super(PointMatchClientModule, self).__init__(
            schema_type=schema_type, *args, **kwargs)

    def run(self):
        
        # prepare sift parameters 
        sift_params = "--SIFTFdSize %d --SIFTsteps %d --matchMaxEpsilon %f --maxFeatureCacheGb %d --SIFTminScale %f --SIFTmaxScale %f --renderScale %f --matchRod %f --matchMinInlierRatio %f --matchMinNumInliers %d --matchMaxNumInliers %d"%(self.args['SIFTFdSize'], self.args['SIFTsteps'], self.args['matchMaxEpsilon'], self.args['maxFeatureCacheGb'], self.args['SIFTminScale'], self.args['SIFTmaxScale'], self.args['renderScale'], self.args['matchRod'], self.args['matchMinInlierRatio'], self.args['matchMinNumInliers'], self.args['matchMaxNumInliers'])
            
        if self.args['method'] == 'qsub':
            temppbs = tempfile.NamedTemporaryFile(
                    suffix=".sh",
                    mode="w",
                    delete=False)
            temppbs.close()
            
            # set the environment variables and the spin_up.pbs in the shell script
            sparkargs = "\" --owner %s --baseDataUrl %s --collection %s pairJson %s %s\""%(self.args['owner'], self.args['baseDataUrl'], self.args['collection'], self.args['pairJson'], sift_params)
            
            env = "sparkhome=%s, sparkjar=%s, sparkclass=%s, sparkargs=%s"%(self.args['sparkhome'], self.args['jarfile'], self.args['className'], sparkargs)
            
            cmd_to_submit = "qsub -l nodes=%d:ppn=%d -q %s -v logdir=%s,%s %s"%(self.args['no_nodes'], self.args['ppn'], self.args['queue_name'], self.args['logdir'], env, self.args['pbs_template'])
            
        elif self.args['method'] == 'spark':
            sparksubmit = os.path.join(self.args['sparkhome'], 'bin', 'spark-submit')
            
            # prepare the spark submit command
            cmd = "%s --master %s --executor-memory %d --class %s %s --baseDataUrl %s --owner %s --collection %s --pairJson %s "%(self.args['masterUrl'], self.args['memory'], self.args['className'], self.args['baseDataUrl'], self.args['collection'], self.args['pairJson'])
            
            cmd_to_submit = cmd + sift_params

        os.system(cmd_to_submit)


if __name__ == "__main__":
    module = PointMatchClientModule(input_data=example)
    #module = PointMatchClientModule(schema_type=PointMatchClientParameters)
    module.run()
