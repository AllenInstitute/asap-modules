import argschema
from argschema.fields import (
        InputDir, OutputDir, Str, Boolean, Nested, List, Int, Float)
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
    baseline_vertices = List(
        Int,
        required=False,
        default=[3, 3],
        missing=[3, 3],
        description=("for [n, m] new ThinPlateSpline transforms will have "
                     " at minimum a grid f n x m control points."))
    mask_epsilon = Float(
        required=False,
        default=10.0,
        missing=10.0,
        description=("parameter epsilon of cv2.approxPolyDP(). Used for converting "
                     "mask contours into control points."))
    recalculate_masks = Boolean(
        required=False,
        default=True,
        missing=True,
        description=("maybe you don't want to spend the time recreating the masks"
                     "and downsampling them. Maybe they are already exactly where they"
                     " should be. For example, re-running with different epsilon."))


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
