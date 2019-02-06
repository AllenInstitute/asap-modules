import argschema
from ..module.schemas import (RenderParameters, ZValueParameters,
                              ProcessPoolParameters)
from argschema.fields import Bool, Str, Float, OutputFile


class FilterSchema(RenderParameters, ZValueParameters, ProcessPoolParameters):
    input_stack = Str(
        required=True,
        description='stack with stage-aligned coordinates')
    input_match_collection = Str(
        required=True,
        description='Name of the montage point match collection')
    output_match_collection = Str(
        required=True,
        default=None,
        missing=None,
        description='Name of the montage point match collection to write to')
    resmax = Float(
        required=True,
        description=("maximum value in "
                     "pixels for average residual in tile pair"))
    transmax = Float(
        required=True,
        description=("maximum value in "
                     "pixels for translation relative to stage coords"))
    filter_output_file = OutputFile(
        required=True,
        description="location of json file with filter output")
    inverse_weighting = Bool(
        required=True,
        default=False,
        missing=False,
        description='new weights weighted inverse to counts per tile-pair')


class FilterOutputSchema(argschema.schemas.DefaultSchema):
    filter_output_file = OutputFile(
        required=True,
        description="location of json file with filter output")
