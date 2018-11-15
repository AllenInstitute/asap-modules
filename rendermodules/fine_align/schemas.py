import argschema
from argschema.fields import InputDir, OutputDir, Str, Boolean, Nested, List
from argschema.schemas import DefaultSchema
from ..module.schemas import (
        InputStackParameters, OutputStackParameters,
        RenderParameters, RenderClientParameters)


class MakeFineInputStackSchema(
        InputStackParameters, OutputStackParameters):
    label_input_dirs = List(
        InputDir,
        required=True,
        cli_as_single_argument=True,
        description=("directories with crack/fold label files "
                     "with names matching tileIDs"))
    mask_output_dir = OutputDir(
        required=True,
        description=("masks OR'ed from previous masks and labels "
                     "will go here."))
    split_divided_tiles = Boolean(
        required=True,
        default=True,
        missing=True,
        description=("if a crack/fold mask clearly divides a tile "
                     "replace the tile with multiple tiles. Can "
                     "aid 3D point match quality."))
    mask_exts = List(
        Str,
        required=False,
        default=['png', 'tif'],
        description="what kind of mask files to recognize") 


class MakeFineOutputStackSchema(DefaultSchema):
    stack = Str(required=True,
        description="output fine stack ready for 3D alignment")


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
