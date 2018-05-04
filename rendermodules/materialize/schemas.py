import argschema
from rendermodules.module.schemas import (
    RenderParameters, SparkParameters, MaterializedBoxParameters,
    ZRangeParameters, RenderParametersRenderWebServiceParameters)
from argschema.fields import (Str, OutputDir, Int, Boolean, Float,
                              List, InputDir)


class RenderSectionAtScaleParameters(RenderParameters):
    input_stack = Str(
        required=True,
        description='Input stack to make the downsample version of')
    image_directory = OutputDir(
        required=True,
        description='Directory to save the downsampled sections')
    imgformat = Str(
        required=False,
        default="png",
        missing="png",
        description='Image format (default -  png)')
    doFilter = Boolean(
        required=False,
        default=True,
        missing=True,
        description='Apply filtering before rendering')
    fillWithNoise = Boolean(
        required=False,
        default=False,
        missing=False,
        description='Fill image with noise (default - False)')
    scale = Float(
        required=True,
        description='scale of the downsampled sections')
    minZ = Int(
        required=False,
        default=-1,
        missing=-1,
        description='min Z to create the downsample section from')
    maxZ = Int(
        required=False,
        default=-1,
        missing=-1,
        description='max Z to create the downsample section from')
    pool_size = Int(
        required=False,
        default=20,
        missing=20,
        description='number of parallel threads to use')


class RenderSectionAtScaleOutput(argschema.schemas.DefaultSchema):
    image_directory = InputDir(
        required=True,
        description='Directory in which the downsampled section images are saved')
    temp_stack = Str(
        required=True,
        description='The temp stack that was used to generate the downsampled sections')


class MaterializeSectionsParameters(
        argschema.ArgSchema, MaterializedBoxParameters,
        ZRangeParameters, RenderParametersRenderWebServiceParameters,
        SparkParameters):
    cleanUpPriorRun = Boolean(required=False, description=(
        "whether to regenerate most recently generated boxes of an "
        "identical plan.  Useful for rerunning failed jobs."))
    explainPlan = Boolean(required=False, description=(
        "whether to perform a dry run, logging as partition stages are run "
        "but skipping materialization"))
    maxImageCacheGb = Float(required=False, default=2.0, description=(
        "maximum image cache in GB of tilespec level 0 data to cache per "
        "core.  Larger values may degrade performance due "
        "to JVM garbage collection."))  # TODO see Eric's
    zValues = List(Int, required=False, description=(
        "z indices to materialize"))


class MaterializeSectionsOutput(argschema.schemas.DefaultSchema):
    zValues = List(Int, required=True)
    rootDirectory = InputDir(required=True)
    materializedDirectory = InputDir(required=True)
