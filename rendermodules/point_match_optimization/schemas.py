from argschema.fields import Bool, Float, Int, Nested, Str, InputDir, OutputDir, List
from argschema.schemas import DefaultSchema
from rendermodules.module.render_module import RenderParameters
from marshmallow import fields


class url_options(DefaultSchema):
    normalizeForMatching = Bool(
        required=False,
        default=True,
        missing=True,
        description='normalize for matching')
    renderWithFilter = Bool(
        required=False,
        default=True,
        missing=True,
        description='Render with Filter')
    renderWithoutMask = Bool(
        required=False,
        default=True,
        missing=True,
        description='Render without mask')

class SIFT_options(DefaultSchema):
    SIFTfdSize = List(
        fields.Int,
        required=False,
        many=True,
        default=[89],
        missing=[89],
        description='SIFT feature descriptor size: how many samples per row and column')
    SIFTmaxScale = List(
        fields.Float,
        required=False,
        many=True,
        default=[0.85],
        missing=[0.85],
        description='SIFT maximum scale: minSize * minScale < size < maxSize * maxScale')
    SIFTminScale = List(
        fields.Float,
        required=False,
        many=True,
        default=[0.5],
        missing=[0.5],
        description='SIFT minimum scale: minSize * minScale < size < maxSize * maxScale')
    SIFTsteps = List(
        fields.Int,
        required=False,
        many=True,
        default=[3],
        missing=[3],
        description='SIFT steps per scale octave')
    matchIterations = List(
        fields.Int,
        required=False,
        default=[1000],
        missing=[1000],
        description='Match filter iterations')
    matchMaxEpsilon = List(
        fields.Float,
        required=False,
        many=True,
        default=[20.0],
        missing=[20.0],
        description='Minimal allowed transfer error for match filtering')
    matchMaxNumInliers = List(
        fields.Int,
        required=False,
        default=[500],
        missing=[500],
        description='Maximum number of inliers for match filtering')
    matchMaxTrust = List(
        fields.Float,
        required=False,
        many=True,
        default=[3.0],
        missing=[3.0],
        description='Reject match candidates with a cost larger than maxTrust * median cost')
    matchMinInlierRatio = List(
        fields.Float,
        required=False,
        many=True,
        default=[0.0],
        missing=[0.0],
        description='Minimal ratio of inliers to candidates for match filtering')
    matchMinNumInliers = List(
        fields.Int,
        required=False,
        default=[8],
        missing=[8],
        description='Minimal absolute number of inliers for match filtering')
    matchModelType = List(
        fields.String,
        required=False,
        default=['AFFINE'],
        missing=['AFFINE'],
        description='Type of model for match filtering Possible Values: [TRANSLATION, RIGID, SIMILARITY, AFFINE]')
    matchRod = List(
        fields.Float,
        required=False,
        many=True,
        default=[0.92],
        missing=[0.92],
        description='Ratio of distances for matches')
    renderScale = List(
        fields.Float,
        required=False,
        many=True,
        default=[0.35],
        missing=[0.35],
        description='Render canvases at this scale')

class PointMatchOptimizationParameters(RenderParameters):
    stack = Str(
        required=True,
        description='Name of the stack containing the tile pair')
    tile_stack = Str(
        required=False,
        default=None,
        description='Name of the stack that will hold these two tiles')
    tileId1 = Str(
        required=True,
        description='tileId of the first tile in the tile pair')
    tileId2 = Str(
        required=True,
        description='tileId of the second tile in the tile pair')
    fillWithNoise = Bool(
        required=False,
        default=False,
        missing=False,
        description='Fill each canvas image with noise before rendering to improve point match derivation')
    pool_size = Int(
        required=False,
        default=10,
        missing=10,
        description='Pool size for parallel processing')
    SIFT_options = Nested(SIFT_options, required=True)
    outputDirectory = OutputDir(
        required=True,
        description='Parent directory in which subdirectories will be created to store images and point-match results from SIFT')
    url_options = Nested(url_options, required=True)
