
from marshmallow import ValidationError, validates_schema, post_load, validate
import argschema
from rendermodules.module.schemas import RenderParameters, RenderClientParameters
from argschema.fields import (Str, OutputDir, Int, Boolean, Float,
                              List, InputDir, InputFile, Dict, Nested)


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



class MaterializedBoxParameters(argschema.schemas.DefaultSchema):
    stack = Str(required=True, description=(
        "stack fromw which boxes will be materialized"))
    rootDirectory = OutputDir(required=True, description=(
        "directory in which materialization directory structure will be "
        "created (structure is "
        "<rootDirectory>/<project>/<stack>/<width>x<height>/<mipMapLevel>/<z>/<row>/<col>.<fmt>)"))
    width = Int(required=True, description=(
        "width of flat rectangular tiles to generate"))
    height = Int(required=True, description=(
        "height of flat rectangular tiles to generate"))
    maxLevel = Int(required=False, default=0, description=(
        "maximum mipMapLevel to generate."))
    fmt = Str(required=False, validator=validate.OneOf(['PNG', 'TIF', 'JPG']),
              description=("image format to generate mipmaps -- "
                           "PNG if not specified"))
    maxOverviewWidthAndHeight = Int(required=False, description=(
        "maximum pixel size for width or height of overview image.  "
        "If excluded or 0, no overview generated."))
    skipInterpolation = Boolean(required=False, description=(
        "whether to skip interpolation (e.g. DMG data)"))
    binaryMask = Boolean(required=False, description=(
        "whether to use binary mask (e.g. DMG data)"))
    label = Boolean(required=False, description=(
        "whether to generate single color tile labels rather "
        "than actual images"))
    createIGrid = Boolean(required=False, description=(
        "whther to create an IGrid file"))
    forceGeneration = Boolean(required=False, description=(
        "whether to regenerate existing tiles"))
    renderGroup = Int(required=False, description=(
        "index (1-n) identifying coarse portion of layer to render"))
    numberOfRenderGroups = Int(required=False, description=(
        "used in conjunction with renderGroup, total number of groups "
        "being used"))


class ZRangeParameters(argschema.schemas.DefaultSchema):
    # TODO how does this work with zValues?
    minZ = Int(required=False, description=("minimum Z integer"))
    maxZ = Int(required=False, description=("maximum Z integer"))


class RenderWebServiceParameters(argschema.schemas.DefaultSchema):
    baseDataUrl = Str(required=False, description=(
        "api endpoint url e.g. http://<host>[:port]/render-ws/v1"))
    owner = Str(required=False, description=("owner of target collection"))
    project = Str(required=False, description=("project fo target collection"))


class RenderParametersRenderWebServiceParameters(RenderWebServiceParameters):
    render = Nested(
        RenderClientParameters, only=['owner', 'project', 'host', 'port'],
        required=False)

    @post_load
    def validate_options(self, data):
        # fill in with render parameters if they are defined
        if data.get('owner') is None:
            data['owner'] = data['render']['owner']
        if data.get('project') is None:
            data['project'] = data['render']['project']
        if data.get('baseDataUrl') is None:
            data['baseDataUrl'] = '{host}{port}/render-ws/v1'.format(
                host=(data['render']['host']
                      if data['render']['host'].startswith(
                      'http') else 'http://{}'.format(data['render']['host'])),
                port=('' if data['render']['port'] is None else ':{}'.format(
                      data['render']['port'])))


class SparkParameters(argschema.schemas.DefaultSchema):
    masterUrl = Str(required=True, description=(
        "spark master url.  For local execution local[num_procs,num_retries]"))
    jarfile = Str(required=True, description=(
        "spark jar to call java spark command"))
    className = Str(required=True, description=(
        "spark class to call"))
    driverMemory = Str(required=False, default='6g', description=(
        "spark driver memory (important for local spark)"))
    # memory = Str(required=False, defaut='6g', description=(""))
    sparkhome = InputDir(required=True, description=(
        "Spark home directory containing bin/spark_submit"))
    spark_files = List(InputFile, required=False, description=(
        "additional files for spark"))
    spark_conf = Dict(required=False, description=(
        "configuration dictionary for spark"))


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
