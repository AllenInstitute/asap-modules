from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
from marshmallow import ValidationError, validates_schema, post_load
from ..module.schemas import RenderParameters



class TilePairClientParameters(RenderParameters):
    stack = Str(
        required=True,
        description="input stack to which tilepairs need to be generated")
    baseStack = Str(
        required=False,
        default=None,
        missing=None,
        description="Base stack")
    minZ = Int(
        required=False,
        default=None,
        missing=None,
        description="z min for generating tilepairs")
    maxZ = Int(
        required=False,
        default=None,
        missing=None,
        description="z max for generating tilepairs")
    xyNeighborFactor = Float(
        required=False,
        default=0.9,
        description="Multiply this by max(width, height) of each tile to determine radius for locating neighbor tiles")
    zNeighborDistance = Int(
        required=False,
        default=2,
        missing=2,
        description="Look for neighbor tiles with z values less than or equal to this distance from the current tile's z value")
    excludeCornerNeighbors = Bool(
        required=False,
        default=True,
        missing=True,
        description="Exclude neighbor tiles whose center x and y is outside the source tile's x and y range respectively")
    excludeSameLayerNeighbors = Bool(
        required=False,
        default=False,
        missing=False,
        description="Exclude neighbor tiles in the same layer (z) as the source tile")
    excludeCompletelyObscuredTiles = Bool(
        required=False,
        default=True,
        missing=True,
        description="Exclude tiles that are completely obscured by reacquired tiles")
    output_dir = Str(
        required=True,
        description="Output directory path to save the tilepair json file")
    memGB = Str(
        required=False,
        default='6G',
        missing='6G',
        description="Memory for the java client to run")

    @validates_schema
    def validate_data(self, data):
        if data['baseStack'] is None:
            data['baseStack'] = data['stack']
