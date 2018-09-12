import argschema
from marshmallow import post_load
from ..module.schemas import (RenderParameters, ZValueParameters,
                              ProcessPoolParameters)
from argschema.fields import Bool, Int, Str, InputDir, Float, OutputFile

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
    overwrite_collection_section = Bool(
        required=True,
        description='delete and overwrite')
    resmax = Float(
        required=True,
        description='maximum value in pixels for average residual in tile pair')
    transmax = Float(
        required=True,
        description='maximum value in pixels for translation relative to stage coords')
    filter_output_file = OutputFile(
        required=True,
        description="location of json file with filter output")


class FilterOutputSchema(argschema.schemas.DefaultSchema):
    filter_output_file = OutputFile(
        required=True,
        description="location of json file with filter output")
