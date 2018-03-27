#!/usr/bin/env python
"""
extract SIFT features using FeatureClient
"""
from rendermodules.module.render_module import SparkModule
from rendermodules.pointmatch.schemas import (
    ExtractFeaturesParameters, ExtractFeaturesOutput)

example_input = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "baseDataUrl": "http://em-131db:8080/render-ws/v1",
    "driverMemory": "40g",
    "sparkhome": "/allen/aibs/pipeline/image_processing/volume_assembly/utils/spark/",
    "masterUrl": "local[*,20]",
    "jarfile": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/dev/render-ws-spark-client-standalone.jar",
    "className":"org.janelia.render.client.spark.FeatureClient",
    "pairJson": "20180326_example_tPairs.json",
    "SIFTfdSize": 8,
    "SIFTsteps": 3,
    "SIFTminScale": 0.38,
    "SIFTmaxScale": 0.82,
    "renderScale": 0.4,
    "rootFeatureDirectory": "/allen/programs/celltypes/workgroups/em-connectomics/russelt/somefeatures/"
}

class ExtractFeaturesModule(SparkModule):
    default_schema = ExtractFeaturesParameters
    default_output_schema = ExtractFeaturesOutput

    @classmethod
    def get_featureextraction_options(cls, baseDataUrl=None,
                                      pairJson=None, SIFTfdSize=None,
                                      SIFTminScale=None, SIFTmaxScale=None,
                                      SIFTsteps=None, clipWidth=None,
                                      clipHeight=None, renderScale=None,
                                      renderWithFilter=None,
                                      renderWithoutMask=None,
                                      renderFullScaleWidth=None,
                                      renderFullScaleHeight=None,
                                      fillWithNoise=None,
                                      rootFeatureDirectory=None, **kwargs):
        get_cmd_opt = cls.get_cmd_opt
        cmd = (
            get_cmd_opt(baseDataUrl, '--baseDataUrl') +
            get_cmd_opt(pairJson, '--pairJson') +
            get_cmd_opt(SIFTfdSize, '--SIFTfdSize') +
            get_cmd_opt(SIFTminScale, '--SIFTminScale') +
            get_cmd_opt(SIFTmaxScale, '--SIFTmaxScale') +
            get_cmd_opt(SIFTsteps, '--SIFTsteps') +
            get_cmd_opt(clipWidth, '--clipWidth') +
            get_cmd_opt(clipHeight, '--clipHeight') +
            get_cmd_opt(renderScale, '--renderScale') +
            get_cmd_opt(renderWithFilter, '--renderWithFilter') +
            get_cmd_opt(renderWithoutMask, '--renderWithoutMask') +
            get_cmd_opt(renderFullScaleWidth, '--renderFullScaleWidth') +
            get_cmd_opt(renderFullScaleHeight, '--renderFullScaleHeight') +
            get_cmd_opt(fillWithNoise, '--fillWithNoise') +
            get_cmd_opt(rootFeatureDirectory, '--rootFeatureDirectory'))
        return cls.sanitize_cmd(cmd)

    @classmethod
    def get_args(cls, **kwargs):
        return cls.get_featureextraction_options(**kwargs)

    def run(self):
        r = self.run_spark_command()
        self.logger.debug("spark run completed with code {}".format(r))
        output_d = {}
        self.output(output_d)


if __name__ == "__main__":
    mod = ExtractFeaturesModule(input_data=example_input)
    mod.run()
