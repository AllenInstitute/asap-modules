
import json
import os
import subprocess
from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
import renderapi
from ..module.render_module import RenderModule, RenderParameters

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
    "sparkhome": "/allen/programs/celltypes/workgroups/em-connectomics/ImageProcessing/utils/spark/",
    "spinup_spark_pbs":"/allen/aibs/shared/image_processing/volume_assembly/utils/code/spark-submit/spinup_spark.pbs",
    "logdir": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/sparkLogs/",
    "jarfile": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-spark-client/target/render-ws-spark-client-0.3.0-SNAPSHOT-standalone.jar",
    "className":"org.janelia.render.client.spark.SIFTPointMatchClient",
    "baseDataUrl":"http://em-131fs:8998/render-ws/v1",
    "owner": "gayathri",
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

class SIFTPointMatchClientParameters(DefaultSchema):
    owner = Str(
        required=True,
        description="Point match collection owner")
    collection = Str(
        required=True,
        description="Name of point match collection to save point matches")
    pairJson = Str(
        required=True,
        description="Full path to the input tile pair json file")
    SIFTfdSize = Int(
        required=False,
        default=8,
        description="SIFT feature descriptor size: how many samples per row and column")
    SIFTsteps = Int(
        required=False,
        default=3,
        description="SIFT steps per scale octave")
    matchMaxEpsilon = Float(
        required=False,
        default=20.0,
        description="Minimal allowed transfer error for match filtering")
    maxFeatureCacheGb = Int(
        required=False,
        default=15,
        description="Maximum memory (in Gb) for caching SIFT features")
    SIFTminScale = Float(
        required=False,
        default=0.38,
        description="SIFT minimum scale: minSize * minScale < size < maxSize * maxScale")
    SIFTmaxScale = Float(
        required=False,
        default=0.82,
        description="SIFT maximum scale: minSize * minScale < size < maxSize * maxScale")
    renderScale = Float(
        required=False,
        default=0.3,
        description="Render canvases at this scale")
    matchRod = Float(
        required=False,
        default=0.92,
        description="Ratio of distances for matches")
    matchMinInlierRatio = Float(
        required=False,
        default=0.0,
        description="Minimal ratio of inliers to candidates for match filtering")
    matchMinNumInliers = Int(
        required=False,
        default=8,
        description="Minimal absolute number of inliers for match filtering")
    matchMaxNumInliers = Int(
        required=False,
        default=200,
        description="Maximum number of inliers for match filtering")

class PointMatchClientParameters(RenderParameters):
    sparkhome = Str(
        required=False,
        default="/allen/aibs/shared/image_processing/volume_assembly/utils/spark",
        description="Path to the spark home directory")
    logdir = Str(
        required=False,
        default="/allen/aibs/shared/image_processing/volume_assembly/logs/spark_logs",
        description="Directory to store spark logs")
    jarfile = Str(
        required=True,
        description="Full path to the spark point match client jar file")
    SIFTParameters = Nested(SIFTPointMatchClientParameters)


class GeneratePointMatchesSpark(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = TilePairClientParameters
        super(TilePairClientModule, self).__init__(
            schema_type=schema_type, *args, **kwargs)




if __name__ == "__main__":
    module = GeneratePointMatchesSpark(input_data=example)
    #module = GeneratePointMatchesSpark(schema_type=PointMatchClientParameters)
    module.run()
