import argschema
from argschema.fields import Str, OutputDir, Int, Boolean, Nested, Float
from marshmallow import validate, post_load

from rendermodules.module.schemas import RenderClientParameters


class MaterializedBoxParameters(argschema.schemas.DefaultSchema):
    stack = Str(required=True, description=(
        "stack fromw which boxes will be materialized"))
    rootDirectory = OutputDir(required=True, description=(
        "directory in which materialization directory structure will be "
        "created (structure is "
        "<rootDirectory>/<project>/<stack>/<width>x<height>/<mipMapLevel>/<z>/<row>/<col>.<fmt>)"))
    width = Int(required=True, description=(
        "width of flat rectangular tiles to generate"))
    height = Int(required=True, description=(
        "height of flat rectangular tiles to generate"))
    maxLevel = Int(required=False, default=0, description=(
        "maximum mipMapLevel to generate."))
    fmt = Str(required=False, validator=validate.OneOf(['PNG', 'TIF', 'JPG']),
              description=("image format to generate mipmaps -- "
                           "PNG if not specified"))
    maxOverviewWidthAndHeight = Int(required=False, description=(
        "maximum pixel size for width or height of overview image.  "
        "If excluded or 0, no overview generated."))
    skipInterpolation = Boolean(required=False, description=(
        "whether to skip interpolation (e.g. DMG data)"))
    binaryMask = Boolean(required=False, description=(
        "whether to use binary mask (e.g. DMG data)"))
    label = Boolean(required=False, description=(
        "whether to generate single color tile labels rather "
        "than actual images"))
    createIGrid = Boolean(required=False, description=(
        "whther to create an IGrid file"))
    forceGeneration = Boolean(required=False, description=(
        "whether to regenerate existing tiles"))
    renderGroup = Int(required=False, description=(
        "index (1-n) identifying coarse portion of layer to render"))
    numberOfRenderGroups = Int(required=False, description=(
        "used in conjunction with renderGroup, total number of groups "
        "being used"))
    filterListName = Str(required=False, description=(
        "Apply specified filter list to all renderings"))


class ZRangeParameters(argschema.schemas.DefaultSchema):
    minZ = Int(required=False, description=("minimum Z integer"))
    maxZ = Int(required=False, description=("maximum Z integer"))


class WebServiceParameters(argschema.schemas.DefaultSchema):
    baseDataUrl = Str(required=False, description=(
        "api endpoint url e.g. http://<host>[:port]/render-ws/v1"))


class RenderWebServiceParameters(WebServiceParameters):
    owner = Str(required=False, description=("owner of target collection"))
    project = Str(required=False, description=("project fo target collection"))


class RenderParametersRenderWebServiceParameters(RenderWebServiceParameters):
    render = Nested(
        RenderClientParameters, only=['owner', 'project', 'host', 'port'],
        required=False)

    @post_load
    def validate_options(self, data):
        # fill in with render parameters if they are defined
        if data.get('owner') is None:
            data['owner'] = data['render']['owner']
        if data.get('project') is None:
            data['project'] = data['render']['project']
        if data.get('baseDataUrl') is None:
            data['baseDataUrl'] = '{host}{port}/render-ws/v1'.format(
                host=(data['render']['host']
                      if data['render']['host'].startswith(
                      'http') else 'http://{}'.format(data['render']['host'])),
                port=('' if data['render']['port'] is None else ':{}'.format(
                      data['render']['port'])))


class FeatureExtractionParameters(argschema.schemas.DefaultSchema):
    SIFTfdSize = Int(required=False, description=(
        "SIFT feature descriptor size -- samples per row and column. "
        "8 if excluded or None"))
    SIFTminScale = Float(required=False, description=(
        "SIFT minimum scale -- "
        "minSize * minScale < size < maxSize * maxScale. "
        "0.5 if excluded or None"))
    SIFTmaxScale = Float(required=False, description=(
        "SIFT maximum scale -- "
        "minSize * minScale < size < maxSize * maxScale. "
        "0.85 if excluded or None"))
    SIFTsteps = Int(required=False, description=(
        "SIFT steps per scale octave. 3 if excluded or None"))


class FeatureRenderClipParameters(argschema.schemas.DefaultSchema):
    clipWidth = Int(required=False, description=(
        "Full scale pixels to include in clipped rendering of "
        "LEFT/RIGHT oriented tile pairs.  Will not LEFT/RIGHT clip if "
        "excluded or None."))
    clipHeight = Int(required=False, description=(
        "Full scale pixels to include in clipped rendering of "
        "TOP/BOTTOM oriented tile pairs.  Will not TOP/BOTTOM clip if "
        "excluded or None."))


class FeatureRenderParameters(argschema.schemas.DefaultSchema):
    renderScale = Float(required=False, description=(
        "Scale at which image tiles will be rendered. "
        "1.0 (full scale) if excluded or None"))
    renderWithFilter = Boolean(required=False, description=(
        "Render tiles using default filtering "
        "(0 and 255 pixel values replaced with integer in U(64, 191), "
        "followed by default NormalizeLocalContrast). "
        "True if excluded or None"))
    renderWithoutMask = Boolean(required=False, description=(
        "Render tiles without mipMapLevel masks. True if excluded or None"))
    renderFullScaleWidth = Int(required=False, description=(
        "Full scale width for all rendered tiles"))
    renderFullScaleHeight = Int(required=False, description=(
        "Full scale height for all rendered tiles"))
    fillWithNoise = Boolean(required=False, description=(
        "Fill each canvas image with noise prior to rendering. "
        "True if excluded or None"))
    renderFilterListName = Str(required=False, description=(
        "Apply specified filter list to all renderings"))


class FeatureStorageParameters(argschema.schemas.DefaultSchema):
    # TODO is this inputdir or outputdir?
    rootFeatureDirectory = Str(required=False, description=(
        "Root directory for saved feature lists. "
        "Features extracted from dynamically rendered canvases "
        "if excluded or None."))
    requireStoredFeatures = Boolean(required=False, description=(
        "Whether to throw an exception in case features stored in "
        "rootFeatureDirectory cannot be found. "
        "Missing features are extracted from dynamically rendered canvases "
        "if excluded or None"))
    maxFeatureCacheGb = Int(required=False, description=(
        "Maximum size of feature cache, in GB. 2GB if excluded or None"))


class MatchDerivationParameters(argschema.schemas.DefaultSchema):
    matchRod = Float(required=False, description=(
        "Ratio of first to second nearest neighbors used as a cutoff in "
        "matching features. 0.92 if excluded or None"))
    matchModelType = Str(required=False, validator=validate.OneOf([
        "AFFINE", "RIGID", "SIMILARITY", "TRANSLATION"]), description=(
        "Model to match for RANSAC filtering. 'AFFINE' if excluded or None"))
    matchIterations = Int(required=False, description=(
        "RANSAC filter iterations.  1000 if excluded or None"))
    matchMaxEpsilon = Float(required=False, description=(
        ""))
    matchMinInlierRatio = Float(required=False, description=(
        "Minimal ratio of inliers to candidates for successful "
        "RANSAC filtering.  0.0 if excluded or None"))
    matchMinNumInliers = Int(required=False, description=(
        "Minimum absolute number of inliers for successful RANSAC filtering. "
        "4 if excluded or None"))
    matchMaxNumInliers = Int(required=False, description=(
        "Maximum absolute number of inliers allowed after RANSAC filtering. "
        "unlimited if excluded or None"))
    matchMaxTrust = Float(required=False, description=(
        "Maximum trust for filtering such that candidates with cost larger "
        "than matchMaxTrust * median cost are rejected. "
        "3.0 if excluded or None"))
    matchFilter = Str(
            required=False,
            validator=validate.OneOf(
                ['SINGLE_SET', 'CONSENSUS_SETS', 'AGGREGATED_CONSENSUS_SETS']),
            description=(
                "whether to match one set of matches, or multiple "
                "sets. And, whether to keep them separate, or aggregate them. "
                "SINGLE_SET if excluded or None."))


class MatchWebServiceParameters(WebServiceParameters):
    owner = Str(required=False, description=("owner of match collection"))
    collection = Str(required=False, description=("match collection name"))


class RenderParametersMatchWebServiceParameters(MatchWebServiceParameters):
    render = Nested(
        RenderClientParameters, only=['owner', 'host', 'port'],
        required=False)

    @post_load
    def validate_options(self, data):
        # fill in with render parameters if they are defined
        if data.get('owner') is None:
            data['owner'] = data['render']['owner']
        if data.get('baseDataUrl') is None:
            data['baseDataUrl'] = '{host}{port}/render-ws/v1'.format(
                host=(data['render']['host']
                      if data['render']['host'].startswith(
                      'http') else 'http://{}'.format(data['render']['host'])),
                port=('' if data['render']['port'] is None else ':{}'.format(
                      data['render']['port'])))
