from argschema.fields import Bool, Float, Int, Nested, Str, InputDir, OutputDir, List, InputFile
from argschema.schemas import DefaultSchema
from marshmallow import ValidationError, post_load
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
        default=False,
        missing=False,
        description='Render without mask')
    excludeAllTransforms = Bool(
        required=False,
        default=False,
        missing=False,
        description="Exclude all transforms")
    excludeFirstTransformAndAllAfter = Bool(
        required=False,
        default=False,
        missing=False,
        description="Exclude first transfrom and all after")
    excludeTransformsAfterLast = Bool(
        required=False,
        default=False,
        missing=False,
        description="Exclude transforms after last")


class SIFT_options(DefaultSchema):
    SIFTfdSize = List(
        fields.Int,
        required=False,
        cli_as_single_argument=True,
        default=[8],
        missing=[8],
        description='SIFT feature descriptor size: how many samples per row and column')
    SIFTmaxScale = List(
        fields.Float,
        required=False,
        cli_as_single_argument=True,
        default=[0.85],
        missing=[0.85],
        description='SIFT maximum scale: minSize * minScale < size < maxSize * maxScale')
    SIFTminScale = List(
        fields.Float,
        required=False,
        cli_as_single_argument=True,
        default=[0.5],
        missing=[0.5],
        description='SIFT minimum scale: minSize * minScale < size < maxSize * maxScale')
    SIFTsteps = List(
        fields.Int,
        required=False,
        cli_as_single_argument=True,
        default=[3],
        missing=[3],
        description='SIFT steps per scale octave')
    matchIterations = List(
        fields.Int,
        required=False,
        default=[1000],
        missing=[1000],
        cli_as_single_argument=True,
        description='Match filter iterations')
    matchMaxEpsilon = List(
        fields.Float,
        required=False,
        cli_as_single_argument=True,
        default=[20.0],
        missing=[20.0],
        description='Minimal allowed transfer error for match filtering')
    matchMaxNumInliers = List(
        fields.Int,
        required=False,
        default=[500],
        missing=[500],
        cli_as_single_argument=True,
        description='Maximum number of inliers for match filtering')
    matchMaxTrust = List(
        fields.Float,
        required=False,
        cli_as_single_argument=True,
        default=[3.0],
        missing=[3.0],
        description='Reject match candidates with a cost larger than maxTrust * median cost')
    matchMinInlierRatio = List(
        fields.Float,
        required=False,
        cli_as_single_argument=True,
        default=[0.0],
        missing=[0.0],
        description='Minimal ratio of inliers to candidates for match filtering')
    matchMinNumInliers = List(
        fields.Int,
        required=False,
        default=[10],
        missing=[10],
        cli_as_single_argument=True,
        description='Minimal absolute number of inliers for match filtering')
    matchModelType = List(
        fields.String,
        required=False,
        default=['AFFINE'],
        missing=['AFFINE'],
        cli_as_single_argument=True,
        description='Type of model for match filtering Possible Values: [TRANSLATION, RIGID, SIMILARITY, AFFINE]')
    matchRod = List(
        fields.Float,
        required=False,
        cli_as_single_argument=True,
        default=[0.92],
        missing=[0.92],
        description='Ratio of distances for matches')
    renderScale = List(
        fields.Float,
        required=False,
        cli_as_single_argument=True,
        default=[0.35],
        missing=[0.35],
        description='Render canvases at this scale')


class PtMatchOptimizationParameters(RenderParameters):
    stack = Str(
        required=True,
        description='Name of the stack containing the tile pair (not the base stack)')
    tile_stack = Str(
        required=False,
        default=None,
        missing=None,
        description='Name of the stack that will hold these two tiles')
    tilepair_file = InputFile(
        required=True,
        description='Tile pair file')
    no_tilepairs_to_test = Int(
        required=False,
        default=10,
        missing=10,
        description='Number of tilepairs to be tested for optimization - default = 10')
    filter_tilepairs = Bool(
        required=False,
        default=False,
        missing=False,
        description="Do you want filter the tilpair file for pairs that overlap? - default = False")
    max_tilepairs_with_matches = Int(
        required=False,
        default=0,
        missing=0,
        description='How many tilepairs with matches required for selection of optimized parameter set')
    numberOfThreads = Int(
        required=False,
        default=5,
        missing=5,
        description='Number of threads to run point matching job')
    SIFT_options = Nested(SIFT_options, required=True)
    outputDirectory = OutputDir(
        required=True,
        description='Parent directory in which subdirectories will be created to store images and point-match results from SIFT')
    url_options = Nested(url_options, required=True)
    pool_size = Int(
        required=False,
        default=10,
        missing=10,
        description='Pool size for parallel processing')
        
    @post_load
    def validate_data(self, data):
        if data['max_tilepairs_with_matches'] == 0:
            data['max_tilepairs_with_matches'] = data['no_tilepairs_to_test']


class PtMatchOptimizationParametersOutput(DefaultSchema):
    output_html = Str(
        required=True,
        description='Output html file that shows all the tilepair plot and results')


class PointMatchOptimizationParameters(RenderParameters):
    stack = Str(
        required=True,
        description='Name of the stack containing the tile pair')
    tile_stack = Str(
        required=False,
        default=None,
        missing=None,
        description='Name of the stack that will hold these two tiles')
    tileId1 = Str(
        required=True,
        description='tileId of the first tile in the tile pair')
    tileId2 = Str(
        required=True,
        description='tileId of the second tile in the tile pair')
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


class PointMatchOptimizationParametersOutput(DefaultSchema):
    output_html = Str(
        required=True,
        description='Output html file that shows all the tilepair plot and results')
        