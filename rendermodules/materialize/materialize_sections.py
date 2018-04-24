#!/usr/bin/env python
"""
Materialize Render sections using BetterBox client
"""
import os

from rendermodules.module.render_module import (RenderModuleException, SparkModule)
from rendermodules.materialize.schemas import (MaterializeSectionsParameters,
                                               MaterializeSectionsOutput)


example_input = {
    "masterUrl": "local[*,20]",
    "jarfile": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/dev/render-ws-spark-client-standalone.jar",
    "className": "org.janelia.render.client.spark.betterbox.BoxClient",
    "driverMemory": "40g",
    "sparkhome": "/allen/aibs/pipeline/image_processing/volume_assembly/utils/spark/",
    "baseDataUrl": "http://em-131fs:8080/render-ws/v1",
    "owner": "russelt",
    "project": "Reflections",
    "stack": "Secs_1015_1099_5_reflections_mml6_rough_affine_scaled",
    "rootDirectory": "/allen/programs/celltypes/workgroups/em-connectomics/russelt/materialize_render/",
    "cleanUpPriorRun": False,
    "maxImageCacheGb": 2.0,  # TODO see Eric's docs
    "zValues": [1015, 1017],
    "width": 1024,
    "height": 1024,
    "maxLevel": 7
}


class MaterializeSectionsError(RenderModuleException):
    pass


class MaterializeSectionsModule(SparkModule):
    default_schema = MaterializeSectionsParameters
    default_output_schema = MaterializeSectionsOutput

    @classmethod
    def get_materialize_options(
            cls, baseDataUrl=None, owner=None, project=None, stack=None,
            rootDirectory=None, width=None, height=None, maxLevel=None,
            fmt=None, maxOverviewWidthAndHeight=None,
            skipInterpolation=None, binaryMask=None, label=None,
            createIGrid=None, forceGeneration=None, renderGroup=None,
            numberOfRenderGroups=None, cleanUpPriorRun=None, explainPlan=None,
            maxImageCacheGb=None, zValues=None, **kwargs):
        get_cmd_opt = cls.get_cmd_opt
        get_flag_cmd = cls.get_flag_cmd

        cmd = (
            get_cmd_opt(baseDataUrl, '--baseDataUrl') +
            get_cmd_opt(owner, '--owner') + get_cmd_opt(project, '--project') +
            get_cmd_opt(stack, '--stack') +
            get_cmd_opt(rootDirectory, '--rootDirectory') +
            get_cmd_opt(width, '--width') + get_cmd_opt(height, '--height') +
            get_cmd_opt(maxLevel, '--maxLevel') +
            get_cmd_opt(fmt, '--format') +
            get_cmd_opt(maxOverviewWidthAndHeight,
                        '--maxOverviewWidthAndHeight') +
            get_flag_cmd(skipInterpolation, '--skipInterpolation') +
            get_flag_cmd(binaryMask, '--binaryMask') +
            get_flag_cmd(label, '--label') +
            get_flag_cmd(createIGrid, '--createIGrid') +
            get_flag_cmd(forceGeneration, '--forceGeneration') +
            get_cmd_opt(renderGroup, '--renderGroup') +
            get_cmd_opt(numberOfRenderGroups, '--numberOfRenderGroups') +
            get_flag_cmd(cleanUpPriorRun, '--cleanUpPriorRun') +
            get_flag_cmd(explainPlan, '--explainPlan') +
            get_cmd_opt(maxImageCacheGb, '--maxImageCacheGb') +
            ([] if zValues is None else ['--z'] + zValues))
        return cls.sanitize_cmd(cmd)

    @classmethod
    def get_args(cls, **kwargs):
        return cls.get_materialize_options(**kwargs)

    def run(self):
        r = self.run_spark_command()
        self.logger.debug("spark run completed with code {}".format(r))
        output_d = {
            'zValues': self.args['zValues'],
            'rootDirectory': self.args['rootDirectory'],
            'materializedDirectory': os.path.join(self.args['rootDirectory'])}
        self.output(output_d)


if __name__ == "__main__":
    mod = MaterializeSectionsModule(input_data=example_input)
    mod.run()
