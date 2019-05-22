from argschema import ArgSchema
from argschema.fields import Bool, Float, Int, Nested, Str, InputFile, List
from argschema.schemas import DefaultSchema
from marshmallow.validate import OneOf
from rendermodules.module.schemas import StackTransitionParameters


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


class ApplyLensCorrectionParameters(StackTransitionParameters):
    transform = Nested(TransformParameters)
    refId = Str(
        allow_none=True, required=True,
        description=('Reference ID to use when uploading transform to '
                     'render database (Not Implemented)'))
    maskUrl = InputFile(
            required=False,
            default=None,
            missing=None,
            description='path to level 0 maskUrl to apply to stack'
            )


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
