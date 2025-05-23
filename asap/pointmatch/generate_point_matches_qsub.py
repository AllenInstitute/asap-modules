#!/usr/bin/env python
import subprocess
import tempfile

from asap.module.render_module import RenderModule
from asap.pointmatch.schemas import PointMatchClientParametersQsub
from asap.pointmatch.generate_point_matches_spark import form_sift_params_list

if __name__ == "__main__" and __package__ is None:
    __package__ = "asap.pointmatch.generate_point_matches_qsub"

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8998,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "no_nodes": 30,
    "ppn": 30,
    "queue_name": "emconnectome",
    "pbs_template": "/allen/aibs/pipeline/image_processing/volume_assembly/utils/code/spark_submit/spinup_spark.pbs",
    "sparkhome": "/allen/programs/celltypes/workgroups/em-connectomics/ImageProcessing/utils/spark/",
    "logdir": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/sparkLogs/",
    "jarfile": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-spark-client/target/render-ws-spark-client-0.3.0-SNAPSHOT-standalone.jar",
    "className": "org.janelia.render.client.spark.SIFTPointMatchClient",
    "baseDataUrl": "http://em-131fs:8998/render-ws/v1",
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


class PointMatchClientModuleQsub(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = PointMatchClientParametersQsub
        super(PointMatchClientModuleQsub, self).__init__(
            schema_type=schema_type, *args, **kwargs)

    def run(self):

        # prepare sift parameters
        sift_params = form_sift_params_list(self.args)

        temppbs = tempfile.NamedTemporaryFile(
                suffix=".sh",
                mode="w",
                delete=False)
        temppbs.close()

        # set the environment variables and the spin_up.pbs in the shell script
        sparkargs = "\" --owner {}".format(self.args['owner'])
        sparkargs += " --baseDataUrl {}".format(self.args['baseDataUrl'])
        sparkargs += " --collection {}".format(self.args['collection'])
        sparkargs += " pairJson {} {}\"".format(
            self.args['pairJson'], " ".join(sift_params))

        env = "sparkhome={},".format(self.args['sparkhome'])
        env += "sparkjar={},".format(self.args['jarfile'])
        env += "sparkclass={},".format(self.args['className'])
        env += "sparkargs={}".format(sparkargs)

        cmd_to_submit = ["qsub", "-l", "nodes={}:ppn={}".format(
            self.args['no_nodes'], self.args['ppn'])]
        cmd_to_submit += ["-q", self.args['queue_name'],
                          "-v", self.args['logdir']]
        cmd_to_submit += [env, self.args['pbs_template']]

        subprocess.check_call(cmd_to_submit)


if __name__ == "__main__":
    module = PointMatchClientModuleQsub()
    module.run()
