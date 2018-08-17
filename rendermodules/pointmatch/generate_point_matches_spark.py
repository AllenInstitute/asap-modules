import json
import os
import subprocess
# from urlparse import urlparse
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse
from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
import renderapi
from rendermodules.module.render_module import RenderModule, RenderModuleException
from rendermodules.module.render_module import SparkModule
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
        l+=["--{}".format(argname),"{}".format(args[argname])]

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


def get_host_port_dict_from_url(url):
    p = urlparse(url)
    return {'host': '{}://{}'.format(p.scheme, p.hostname),
            'port': p.port}

class PointMatchClientModuleSpark(SparkModule):
    default_schema = PointMatchClientParametersSpark
    default_output_schema = PointMatchClientOutputSchema

    @classmethod
    def get_pointmatch_args(cls, baseDataUrl=None, owner=None,
                            collection=None, pairJson=None, SIFTfdSize=None,
                            SIFTminScale=None, SIFTmaxScale=None,
                            SIFTsteps=None, matchRod=None,
                            matchModelType=None, matchIterations=None,
                            matchMaxEpsilon=None, matchMinInlierRatio=None,
                            matchMinNumInliers=None, matchMaxNumInliers=None,
                            matchMaxTrust=None, maxFeatureCacheGb=None,
                            clipWidth=None, clipHeight=None, renderScale=None,
                            renderWithFilter=None, renderWithoutMask=None,
                            renderFullScaleWidth=None,
                            renderFullScaleHeight=None, fillWithNoise=None,
                            rootFeatureDirectory=None,
                            renderFilterListName=None,
                            requireStoredFeatures=None,
                            **kwargs):
        get_cmd_opt = cls.get_cmd_opt
        cmd = (
            get_cmd_opt(baseDataUrl, '--baseDataUrl') +
            get_cmd_opt(owner, '--owner') +
            get_cmd_opt(collection, '--collection') +
            get_cmd_opt(pairJson, '--pairJson') +
            get_cmd_opt(SIFTfdSize, '--SIFTfdSize') +
            get_cmd_opt(SIFTminScale, '--SIFTminScale') +
            get_cmd_opt(SIFTmaxScale, '--SIFTmaxScale') +
            get_cmd_opt(SIFTsteps, '--SIFTsteps') +
            get_cmd_opt(matchRod, '--matchRod') +
            get_cmd_opt(matchModelType, '--matchModelType') +
            get_cmd_opt(matchIterations, '--matchIterations') +
            get_cmd_opt(matchMaxEpsilon, '--matchMaxEpsilon') +
            get_cmd_opt(matchMinInlierRatio, '--matchMinInlierRatio') +
            get_cmd_opt(matchMinNumInliers, '--matchMinNumInliers') +
            get_cmd_opt(matchMaxNumInliers, '--matchMaxNumInliers') +
            get_cmd_opt(matchMaxTrust, '--matchMaxTrust') +
            get_cmd_opt(maxFeatureCacheGb, '--maxFeatureCacheGb') +
            get_cmd_opt(clipWidth, '--clipWidth') +
            get_cmd_opt(clipHeight, '--clipHeight') +
            get_cmd_opt(renderScale, '--renderScale') +
            get_cmd_opt(renderWithFilter, '--renderWithFilter') +
            get_cmd_opt(renderWithoutMask, '--renderWithoutMask') +
            get_cmd_opt(renderFullScaleWidth, '--renderFullScaleWidth') +
            get_cmd_opt(renderFullScaleHeight, '--renderFullScaleHeight') +
            get_cmd_opt(fillWithNoise, '--fillWithNoise') +
            get_cmd_opt(renderFilterListName, '--renderFilterListName') +
            get_cmd_opt(rootFeatureDirectory, '--rootFeatureDirectory') +
            cls.get_flag_cmd(requireStoredFeatures, '--requireStoredFeatures'))
        return cmd

    @classmethod
    def get_args(cls, **kwargs):
        return cls.sanitize_cmd(cls.get_pointmatch_args(**kwargs))


    def run(self):
        r = self.run_spark_command()
        self.logger.debug("spark run completed with code {}".format(r))



        # FIXME render object should be able to initialize without needing to be RenderModule
        mc = renderapi.pointmatch.get_matchcollections(
            self.args['owner'], **get_host_port_dict_from_url(
                self.args['baseDataUrl']))

        collection = next(
            m for m in mc if m['collectionId']['name'] ==
            self.args['collection'])
        self.output(collection)


if __name__ == "__main__":
    module = PointMatchClientModuleSpark(input_data=example)
    #module = PointMatchClientModuleSpark(schema_type=PointMatchClientParameters)
    module.run()
