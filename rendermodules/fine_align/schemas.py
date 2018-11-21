import argschema
from argschema.fields import (
        InputDir, OutputDir, Str, Boolean,
        Nested, List, Int, Float, OutputFile)
from argschema.schemas import DefaultSchema
from ..module.schemas import (
        InputStackParameters, OutputStackParameters,
        RenderParameters, RenderClientParameters,
        ProcessPoolParameters)


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


class MakePairJsonShapelySchema(InputStackParameters, ProcessPoolParameters):
    output_dir = OutputDir(
        required=True,
        description="Output directory path to save the tilepair json file")
    zNeighborDistance = Int(
        required=False,
        default=2,
        missing=2,
        description="Look for neighbor tiles with z values less than "
                    "or equal to this distance from the current tile's z value")
    buffer_pixels = Int(
        required=False,
        default=200,
        missing=200,
        description="passed to shapely Polygon.buffer() to accout for imperfect "
                    " rough alignment")
    excludeSameLayerNeighbors = Boolean(
        required=False,
        default=False,
        missing=False,
        description="Exclude neighbor tiles in the "
                    "same layer (z) as the source tile")
    compress_output = Boolean(
        required=False,
        default=True,
        missing=True,
        description="write tilepair in json.gz format?")


class MakePairJsonShapelyOutputSchema(DefaultSchema):
    tile_pair_file = OutputFile(
        required=True,
        description="location of json file with tile pair inputs")


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
