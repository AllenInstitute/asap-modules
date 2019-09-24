from argschema import ArgSchema
from argschema.fields import Bool, Float, Int, Nested, Str, InputFile, List, Dict
from argschema.schemas import DefaultSchema
from marshmallow.validate import OneOf
import marshmallow

from rendermodules.module.schemas import StackTransitionParameters
import rendermodules.utilities.schema_utils


class TransformParameters(DefaultSchema):
    type = Str(
        required=True,
        validator=OneOf(["leaf", "interpolated", "list", "ref"]),
        description=('Transform type as defined in Render Transform Spec.  '
                     'This module currently expects a "leaf"'))
    className = Str(
        required=True,
        description='mpicbg-compatible className')
    dataString = Str(
        required=True,
        description='mpicbg-compatible dataString')
    metaData = Dict(
        required=False,
        description="in this schema, otherwise will be stripped")


class ApplyLensCorrectionParameters(StackTransitionParameters):
    transform = Nested(TransformParameters)
    refId = Str(
        allow_none=True, required=True,
        description=('Reference ID to use when uploading transform to '
                     'render database (Not Implemented)'))
    labels = List(
        Str,
        required=True,
        missing=['lens'],
        default=['lens'],
        description="labels for the lens correction transform")
    maskUrl = InputFile(
            required=False,
            default=None,
            missing=None,
            description='path to level 0 maskUrl to apply to stack'
            )
    maskUrl_uri = Str(
        required=False,
        default=None,
        missing=None,
        description="uri for level 0 mask image to apply")

    @marshmallow.pre_load
    def maskUrl_to_uri(self, data):
        rendermodules.utilities.schema_utils.posix_to_uri(
            data, "maskUrl", "maskUrl_uri")


class ApplyLensCorrectionOutput(DefaultSchema):
    stack = Str(required=True,
                description='stack to which transformed tiles were written')
    refId = Str(required=True,
                description='unique identifier string used as reference ID')
    missing_ts_zs = List(Int,
        required=False,
        default=[],
        missing=[],
        cli_as_single_argument=True,
        description="Z values for which apply mipmaps failed")
