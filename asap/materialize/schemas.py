import warnings

import argschema
from argschema.fields import (Str, OutputDir, Int, Boolean, Float,
                              List, InputDir, Nested)
import marshmallow
from marshmallow import post_load

from asap.module.schemas import (
    RenderParameters, SparkParameters, MaterializedBoxParameters,
    ZRangeParameters, RenderParametersRenderWebServiceParameters)


class Bounds(argschema.schemas.DefaultSchema):
    minX = Int(
        required=False,
        default=None,
        missing=None,
        description="minX of bounds")
    maxX = Int(
        required=False,
        default=None,
        missing=None,
        description="maxX of bounds")
    minY = Int(
        required=False,
        default=None,
        missing=None,
        description="minY of bounds")
    maxY = Int(
        required=False,
        default=None,
        missing=None,
        description="maxY of bounds")


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
    filterListName = Str(required=False, description=(
        "Apply specified filter list to all renderings"))
    bounds = Nested(Bounds, required=False, default=None, missing=None)
    use_stack_bounds = Boolean(
        required=False,
        default=False,
        missing=False,
        description=('Do you want to use stack bounds '
                     'while downsampling?. Default=False'))
    pool_size = Int(
        required=False,
        default=20,
        missing=20,
        description='number of parallel threads to use')

    @post_load
    def validate_data(self, data):
        # FIXME will be able to remove with render-python tweak
        if data.get('filterListName') is not None:
            warnings.warn(
                "filterListName not implemented -- will use default behavior",
                UserWarning)


class RenderSectionAtScaleOutput(argschema.schemas.DefaultSchema):
    image_directory = InputDir(
        required=True,
        description=('Directory in which the downsampled '
                     'section images are saved'))
    temp_stack = Str(
        required=True,
        description=('The temp stack that was used to '
                     'generate the downsampled sections'))


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


# materialization validation schemas
class ValidateMaterializationParameters(argschema.ArgSchema):
    # TODO allow row, column, validate min & max
    minRow = argschema.fields.Int(required=False, description=(
        "minimum row to attempt to validate tiles. "
        "Will attempt to use stack bounds if None"))
    maxRow = argschema.fields.Int(required=False)
    minCol = argschema.fields.Int(required=False)
    maxCol = argschema.fields.Int(required=False)
    minZ = argschema.fields.Int(required=True)
    maxZ = argschema.fields.Int(required=True)
    ext = argschema.fields.Str(required=False, default="png",
                               validator=marshmallow.validate.OneOf(
                                   ["png", "jpg", "tif"]))
    basedir = argschema.fields.InputDir(required=True, description=(
        "base directory for materialization"))
    pool_size = argschema.fields.Int(required=False, description=(
        "size of pool to use to investigate image validity"))


class ValidateMaterializationOutput(argschema.schemas.DefaultSchema):
    basedir = argschema.fields.Str(required=True)
    # TODO this should probably be an InputFile unless we're disallowing ENOENT
    failures = argschema.fields.List(argschema.fields.Str, required=True)


class DeleteMaterializedSectionsParameters(argschema.ArgSchema):
    minZ = argschema.fields.Int(required=True)
    maxZ = argschema.fields.Int(required=True)
    basedir = argschema.fields.InputDir(required=True, description=(
        "base directory for materialization"))
    pool_size = argschema.fields.Int(required=False, description=(
        "size of pool to use to delete files"))
    tilesource = argschema.fields.Int(required=False, default=5)


class DeleteMaterializedSectionsOutput(argschema.schemas.DefaultSchema):
    pass
