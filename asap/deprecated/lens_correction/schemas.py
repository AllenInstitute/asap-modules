from argschema import ArgSchema
from argschema.schemas import DefaultSchema
from argschema.fields import Int, Float, Bool, InputFile, Nested, Str


class SIFTParameters(DefaultSchema):
    initialSigma = Float(
        required=True,
        description="initial sigma value for SIFT's gaussian blur, in pixels")
    steps = Int(
        required=True,
        description='steps per SIFT scale octave')
    minOctaveSize = Int(
        required=True,
        description='minimum image size used for SIFT octave, in pixels')
    maxOctaveSize = Int(
        required=True,
        description='maximum image size used for SIFT octave, in pixels')
    fdSize = Int(
        required=True,
        description='SIFT feature descriptor size')
    fdBins = Int(
        required=True,
        description='SIFT feature descriptor orientation bins')


class AlignmentParameters(DefaultSchema):
    rod = Float(
        required=True,
        description='ratio of distances for matching SIFT features')
    maxEpsilon = Float(
        required=True,
        description='maximum acceptable epsilon for RANSAC filtering')
    minInlierRatio = Float(
        required=True,
        description='minimum inlier ratio for RANSAC filtering')
    minNumInliers = Int(
        required=True,
        description='minimum number of inliers for RANSAC filtering')
    expectedModelIndex = Int(
        required=True,
        description=('expected model for RANSAC filtering, 0=Translation, '
                     '1="Rigid", 2="Similarity", 3="Affine"'))
    multipleHypotheses = Bool(
        required=True,
        description=('Utilize RANSAC filtering which allows '
                     'fitting multiple hypothesis models'))
    rejectIdentity = Bool(
        required=True,
        description=('Reject Identity model (constant background) '
                     'up to a tolerance defined by identityTolerance'))
    identityTolerance = Float(
        required=True,
        description='Tolerance to which Identity should rejected, in pixels')
    tilesAreInPlace = Bool(
        required=True,
        description=('Whether tile inputs to TrakEM2 are in place to be '
                     'compared only to neighboring tiles.'))
    desiredModelIndex = Int(
        required=True,
        description=('Affine homography model which optimization will '
                     'try to fit, 0="Translation", 1="Rigid", '
                     '2="Similarity", 3="Affine"'))
    # TODO no input for regularizer model, defaults to Rigid regularization
    regularize = Bool(
        required=True,
        description=('Whether to regularize the desired model with '
                     'the regularizer model by lambda'))
    maxIterationsOptimize = Int(
        required=True,
        description='Max number of iterations for optimizer')
    maxPlateauWidthOptimize = Int(
        required=True,
        description='Maximum plateau width for optimizer')
    dimension = Int(
        required=True,
        description=('Dimension of polynomial kernel to fit '
                     'for distortion model'))
    lambdaVal = Float(
        required=True,
        description=('Lambda parameter by which the regularizer model '
                     'affects fitting of the desired model'))
    clearTransform = Bool(
        required=True,
        description=('Whether to remove transforms from tiles '
                     'before SIFT matching.  Not recommended'))
    visualize = Bool(
        required=True,
        description=('Whether to have TrakEM2 visualize the lens '
                     'correction transform.  Not recommended when '
                     'running through xvfb'))


class LensCorrectionParameters(ArgSchema):
    manifest_path = InputFile(
        required=True,
        description='path to manifest file')
    project_path = Str(
        required=True,
        description='path to project directory')
    fiji_path = InputFile(
        required=True,
        description='path to FIJI')
    grid_size = Int(
        required=True,
        description=('maximum row and column to form square '
                     'subset of tiles starting from zero (based on filenames '
                     'which end in "\{row\}_\{column\}.tif")'))
    heap_size = Int(
        required=False,
        default=20,
        description="memory in GB to allocate to Java heap")
    outfile = Str(
        required=False,
        description=("File to which json output of lens correction "
                     "(leaf TransformSpec) is written"))
    processing_directory = Str(
        required=False,
        allow_none=True,
        description=("directory to which trakem2 processing "
                     "directory will be written "
                     "(will place in project_path directory if "
                     "unspecified or create temporary directory if None)"))
    SIFT_params = Nested(SIFTParameters)
    align_params = Nested(AlignmentParameters)
    max_threads_SIFT = Int(
        required=False, default=3, description=(
            "Threads specified for SIFT"))


class LensCorrectionOutput(DefaultSchema):
    # TODO probably easier to output the resulting file via python
    output_json = Str(required=True,
                      description='path to file ')
