from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
from marshmallow import Schema, validates_schema, post_load
from ..module.render_module import RenderParameters


class SolverParameters(DefaultSchema):
    min_tiles = Int(
        required=False,
        default=3,
        missing=3,
        description="Minimum number of tiles in section")
    degree = Int(
        required=False,
        default=1,
        missing=1,
        description="Degree of rquired transformation (0 - Rigid, 1 - Affine(default), 2 - Polynomial)")
    outlier_lambda = Int(
        required=False,
        default=1000,
        missing=1000,
        description="lambda value for outliers")
    solver = Str(
        required=False,
        default="backslash",
        missing="backslash",
        description="type of solver to solve the system (default - backslash)")
    min_points = Int(
        required=False,
        default=4,
        missing=4,
        description="Minimum number of points correspondences required per tile pair")
    max_points = Int(
        required=False,
        default=80,
        missing=80,
        description="Maximum number of point correspondences required per tile pair")
    stvec_flag = Int(
        required=False,
        default=0,
        missing=0,
        description="stvec flag for solver (default - 0)")
    conn_comp = Int(
        required=False,
        default=1,
        missing=1,
        description="Connected components")
    distributed = Int(
        required=False,
        default=0,
        missing=0,
        description="Distributed parameter of solver")
    lambda_value = Float(
        required=False,
        default=1,
        missing=1,
        description="lambda for the solver")
    edge_lambda = Float(
        required=False,
        default=0.1,
        missing=0.1,
        description="edge lambda for solver regularization")
    small_region_lambda = Float(
        required=False,
        default=10,
        missing=10,
        description="small region lambda")
    small_region = Int(
        required=False,
        default=5,
        missing=5,
        description="small region")
    calc_confidence = Int(
        required=False,
        default=1,
        missing=1,
        description="Calculate confidence? (default = 1)")
    translation_fac = Int(
        required=False,
        default=1,
        missing=1,
        description="translation factor")
    use_peg = Int(
        required=False,
        default=1,
        missing=1,
        description="Use pegs? (default = 1)")
    peg_weight = Float(
        required=False,
        default=0.0001,
        missing=0.0001,
        description="Peg weight")
    peg_npoints = Int(
        required=False,
        default=5,
        missing=5,
        description="Number of peg points")

class BaseStackParameters(DefaultSchema):
    stack = Str(
        required=True,
        description="Stack name")
    owner = Str(
        required=False,
        default=None,
        missing=None,
        description="Owner of the stack (defaults to render clients' owner)")
    project = Str(
        required=False,
        default=None,
        missing=None,
        description="Project of the stack")
    service_host = Str(
        required=False,
        default=None,
        missing=None,
        description="url of render service host (without http://)")
    baseURL = Str(
        required=False,
        default=None,
        missing=None,
        description="Base Render URL")
    renderbinPath = InputDir(
        required=False,
        default=None,
        missing=None,
        description="Path to render's client scripts")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="Verbose output from solver needed?")

class SourceStackParameters(BaseStackParameters):
    pass


class TargetStackParameters(BaseStackParameters):
    initialize = Int(
        required=False,
        default=0,
        missing=0,
        description="Do you want to initialize the stack from scratch")


class PointMatchCollectionParameters(DefaultSchema):
    server = Str(
        required=False,
        default=None,
        missing=None,
        description="Render server's base URL")
    owner = Str(
        required=False,
        default=None,
        missing=None,
        description="Owner of the point match collection (default - render service owner)")
    match_collection = Str(
        required=True,
        description="Montage point match collection")


class SolveMontageSectionParameters(RenderParameters):
    z_value = Int(
        required=True,
        description="Z value of section to be montaged")
    filter_point_matches = Int(
        required=False,
        default=1,
        missing=1,
        description="Do you want to filter point matches? default - 1")
    solver_executable = Str(
        required=True,
        description="Matlab solver executable with full path")
    temp_dir = InputDir(
        required=True,
        default="/allen/aibs/shared/image_processing/volume_assembly/scratch",
        description="Path to temporary directory")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="Verbose output from solver needed?")
    dir_scratch = InputDir(
        required=True,
        default="/allen/aibs/shared/image_processing/volume_assembly/scratch",
        description="Path to scratch directory - can be the same as temp_dir")
    renderer_client = Str(
        required=False,
        default=None,
        missing=None,
        description="Path to render client script render.sh")
    solver_options = Nested(
        SolverParameters,
        required=True,
        description="Solver parameters")
    source_collection = Nested(
        SourceStackParameters,
        required=True,
        description="Input stack parameters")
    target_collection = Nested(
        TargetStackParameters,
        required=True,
        description="Output stack parameters")
    source_point_match_collection = Nested(
        PointMatchCollectionParameters,
        required=True,
        description="Point match collection parameters")

    @post_load
    def add_missing_values(self, data):
        # cannot create "lambda" as a variable name in SolverParameters
        data['solver_options']['lambda'] = data['solver_options']['lambda_value']
        data['solver_options'].pop('lambda_value', None)

        if data['renderer_client'] is None:
            data['renderer_client'] = os.path.join(data['render']['client_scripts'], 'render.sh')

        if data['source_collection']['owner'] is None:
            data['source_collection']['owner'] = data['render']['owner']
        if data['source_collection']['project'] is None:
            data['source_collection']['project'] = data['render']['project']
        if data['source_collection']['service_host'] is None:
            data['source_collection']['service_host'] = data['render']['host'][7:] + ":" + str(data['render']['port'])
        if data['source_collection']['baseURL'] is None:
            data['source_collection']['baseURL'] = data['render']['host'] + ":" + str(data['render']['port']) + '/render-ws/v1'
        if data['source_collection']['renderbinPath'] is None:
            data['source_collection']['renderbinPath'] = data['render']['client_scripts']

        if data['target_collection']['owner'] is None:
            data['target_collection']['owner'] = data['render']['owner']
        if data['target_collection']['project'] is None:
            data['target_collection']['project'] = data['render']['project']
        if data['target_collection']['service_host'] is None:
            data['target_collection']['service_host'] = data['render']['host'][7:] + ":" + str(data['render']['port'])
        if data['target_collection']['baseURL'] is None:
            data['target_collection']['baseURL'] = data['render']['host'] + ":" + str(data['render']['port']) + '/render-ws/v1'
        if data['target_collection']['renderbinPath'] is None:
            data['target_collection']['renderbinPath'] = data['render']['client_scripts']

        if data['source_point_match_collection']['server'] is None:
            data['source_point_match_collection']['server'] = data['source_collection']['baseURL']
        if data['source_point_match_collection']['owner'] is None:
            data['source_point_match_collection']['owner'] = data['render']['owner']
