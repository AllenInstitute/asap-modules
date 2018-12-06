import argschema
from ..module.schemas import (RenderParameters, ZValueParameters,
                              ProcessPoolParameters)
from argschema.fields import Bool, Str, Float, OutputFile, Int


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
    zNeighborDistance = Int(
        required=False,
        default=2,
        missing=2,
        description="Look between neighboring sections with z values less than "
                    "or equal to this distance from the current tile's z value")
    excludeSameLayerNeighbors = Bool(
        required=False,
        default=False,
        missing=False,
        description="Exclude neighbor tiles in the "
                    "same layer (z) as the source tile")
    compare_translation_to_tform_label = Str(
        required=False,
        default="rough",
        missing="rough",
        allow_none=True,
        description="compare translations to transforms with this label")
    compare_translation_to_tform_index = Int(
        required=False,
        default=-1,
        missing=-1,
        allow_none=True,
        description="compare translations to transforms with this index."
                    "overrides compare_translation_to_tform_str")


class FilterOutputSchema(argschema.schemas.DefaultSchema):
    filter_output_file = OutputFile(
        required=True,
        description="location of json file with filter output")
