import argschema
from argschema.fields import InputDir, OutputDir, Str, Boolean, Nested
from ..module.schemas import (
        InputStackParameters, OuputStackParameters,
        RenderParameters, RenderClientParameters)


class MakeFineInputStackSchema(
        InputStackParameters, OutputStackParameters):
    mask_input_dir = InputDir(
        required=True,
        description=("location of crack/fold label files "
                     "with names matching tileIDs"))
    mask_output_dir = OutputDir(
        required=True,
        description=("if the tilespecs already have a "
                     "mask from lens correction, the OR'ed masks "
                     "will go here."))
    split_divided_tiles = Boolean(
        required=True,
        default=False,
        missing=False,
        description=("if a crack/fold mask clearly divides a tile "
                     "replace the tile with multiple tiles. Can "
                     "aid 3D point match quality.")


class FilterPointMatchesByMaskSchema(InputStackParameters):
    input_match_collection = Str(
        required=True,
        description=("collection whose point matches will be checked" 
                     "against masked region."))
    output_match_collection = Str(
        required=True,
        default=None,
        missing=None,
        description=("new or overwrite collection, with zero weights in "
                     "masked region."))
    collection_render = Nested(RenderClientParameters)
