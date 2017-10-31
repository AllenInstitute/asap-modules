from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
from marshmallow import ValidationError, validates_schema, post_load
from rendermodules.module.schemas import RenderParameters



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

    @post_load
    def validate_data(self, data):
        if data['baseStack'] is None:
            data['baseStack'] = data['stack']


#class SIFTPointMatchClientParameters(DefaultSchema):

class PointMatchClientParametersSpark(RenderParameters):
    memory = Str(
        required=False,
        default='120g',
        missing='120g',
        description="Memory required for spark job")
    masterUrl = Str(
        required=True,
        description="Master URL for spark cluster")
    sparkhome = Str(
        required=True,
        default="/allen/aibs/shared/image_processing/volume_assembly/utils/spark",
        missing="/allen/aibs/shared/image_processing/volume_assembly/utils/spark",
        description="Path to the spark home directory")
    logdir = Str(
        required=False,
        default="/allen/aibs/shared/image_processing/volume_assembly/logs/spark_logs",
        missing="/allen/aibs/shared/image_processing/volume_assembly/logs/spark_logs",
        description="Directory to store spark logs")
    jarfile = Str(
        required=True,
        description="Full path to the spark point match client jar file")
    className = Str(
        required=True,
        description="Class name of java class")
    owner = Str(
        required=False,
        default=None,
        missing=None,
        description="Point match collection owner")
    collection = Str(
        required=True,
        description="Name of point match collection to save point matches")
    baseDataUrl = Str(
        required=False,
        default=None,
        missing=None,
        description="Base data URL of render")
    pairJson = Str(
        required=True,
        description="Full path to the input tile pair json file")
    SIFTfdSize = Int(
        required=False,
        default=8,
        missing=8,
        description="SIFT feature descriptor size: how many samples per row and column")
    SIFTsteps = Int(
        required=False,
        default=3,
        missing=3,
        description="SIFT steps per scale octave")
    matchMaxEpsilon = Float(
        required=False,
        default=20.0,
        missing=20.0,
        description="Minimal allowed transfer error for match filtering")
    maxFeatureCacheGb = Int(
        required=False,
        default=15,
        missing=15,
        description="Maximum memory (in Gb) for caching SIFT features")
    SIFTminScale = Float(
        required=False,
        default=0.38,
        missing=0.38,
        description="SIFT minimum scale: minSize * minScale < size < maxSize * maxScale")
    SIFTmaxScale = Float(
        required=False,
        default=0.82,
        missing=0.82,
        description="SIFT maximum scale: minSize * minScale < size < maxSize * maxScale")
    renderScale = Float(
        required=False,
        default=0.3,
        missing=0.3,
        description="Render canvases at this scale")
    matchRod = Float(
        required=False,
        default=0.92,
        missing=0.92,
        description="Ratio of distances for matches")
    matchMinInlierRatio = Float(
        required=False,
        default=0.0,
        missing=0.0,
        description="Minimal ratio of inliers to candidates for match filtering")
    matchMinNumInliers = Int(
        required=False,
        default=8,
        missing=8,
        description="Minimal absolute number of inliers for match filtering")
    matchMaxNumInliers = Int(
        required=False,
        default=200,
        description="Maximum number of inliers for match filtering")

    @post_load
    def validate_options(self, data):
        if data['owner'] is None:
            data['owner'] = data['render']['owner']
        if data['baseDataUrl'] is None:
            data['baseDataUrl'] = 'http://' + data['render']['host'] + ":" + str(data['render']['port']) + "/render-ws/v1"

class PointMatchClientParametersQsub(RenderParameters):
    sparkhome = Str(
        required=True,
        default="/allen/aibs/shared/image_processing/volume_assembly/utils/spark",
        missing="/allen/aibs/shared/image_processing/volume_assembly/utils/spark",
        description="Path to the spark home directory")
    pbs_template = Str(
        required=True,
        description="pbs template to wrap spark job")
    no_nodes = Int(
        required=False,
        default=30,
        missing=10,
        description='Number of nodes to run the pbs job')
    ppn = Int(
        required=False,
        default=30,
        missing=30,
        description='Number of processors per node (default = 30)')
    queue_name = Str(
        required=False,
        default='connectome',
        missing='connectome',
        description='Name of the queue to submit the job')
    logdir = Str(
        required=False,
        default="/allen/aibs/shared/image_processing/volume_assembly/logs/spark_logs",
        missing="/allen/aibs/shared/image_processing/volume_assembly/logs/spark_logs",
        description="Directory to store spark logs")
    jarfile = Str(
        required=True,
        description="Full path to the spark point match client jar file")
    className = Str(
        required=True,
        description="Class name of java class")
    owner = Str(
        required=False,
        default=None,
        missing=None,
        description="Point match collection owner")
    collection = Str(
        required=True,
        description="Name of point match collection to save point matches")
    baseDataUrl = Str(
        required=False,
        default=None,
        missing=None,
        description="Base data URL of render")
    pairJson = Str(
        required=True,
        description="Full path to the input tile pair json file")
    SIFTfdSize = Int(
        required=False,
        default=8,
        missing=8,
        description="SIFT feature descriptor size: how many samples per row and column")
    SIFTsteps = Int(
        required=False,
        default=3,
        missing=3,
        description="SIFT steps per scale octave")
    matchMaxEpsilon = Float(
        required=False,
        default=20.0,
        missing=20.0,
        description="Minimal allowed transfer error for match filtering")
    maxFeatureCacheGb = Int(
        required=False,
        default=15,
        missing=15,
        description="Maximum memory (in Gb) for caching SIFT features")
    SIFTminScale = Float(
        required=False,
        default=0.38,
        missing=0.38,
        description="SIFT minimum scale: minSize * minScale < size < maxSize * maxScale")
    SIFTmaxScale = Float(
        required=False,
        default=0.82,
        missing=0.82,
        description="SIFT maximum scale: minSize * minScale < size < maxSize * maxScale")
    renderScale = Float(
        required=False,
        default=0.3,
        missing=0.3,
        description="Render canvases at this scale")
    matchRod = Float(
        required=False,
        default=0.92,
        missing=0.92,
        description="Ratio of distances for matches")
    matchMinInlierRatio = Float(
        required=False,
        default=0.0,
        missing=0.0,
        description="Minimal ratio of inliers to candidates for match filtering")
    matchMinNumInliers = Int(
        required=False,
        default=8,
        missing=8,
        description="Minimal absolute number of inliers for match filtering")
    matchMaxNumInliers = Int(
        required=False,
        default=200,
        description="Maximum number of inliers for match filtering")


    @post_load
    def validate_options(self, data):
        if data['owner'] is None:
            data['owner'] = data['render']['owner']
        if data['baseDataUrl'] is None:
            data['baseDataUrl'] = 'http://' + data['render']['host'] + ":" + str(data['render']['port']) + "/render-ws/v1"
