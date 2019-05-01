from argschema.fields import Bool, Float, Int, Nested, Str, InputDir, OutputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
from marshmallow import Schema, validates_schema, post_load
from ..module.render_module import RenderParameters
from rendermodules.rough_align.schemas import *
import os


class PointMatchFilteringOptions(DefaultSchema):
    NumRandomSamplingsMethod = Str(
        required=False,
        default="Desired confidence",
        missing="Desired confidence",
        description="Numerical random sampling method")
    MaximumRandomSamples = Int(
        required=False,
        default=5000,
        missing=5000,
        description="Max number of random samples")
    DesiredConfidence = Float(
        required=False,
        default=99.9,
        missing=99.9,
        description="Desired confidence value for point match filtering")
    Transform = Str(
        required=False,
        default="Affine",
        missing="Affine",
        description="RANSAC model to fit")
    PixelDistanceThreshold = Float(
        required=False,
        default=0.1,
        missing=0.1,
        description="Pixel distance threshold")


class PastixOptions(DefaultSchema):
    ncpus = Int(
        required=False,
        default=8,
        missing=8,
        description="number of cpu cores to be used for solving")
    parms_fn = Str(
        required=True,
        description="pastix parameters in a file")
    split = Int(
        required=False,
        default=1,
        missing=1,
        description="split parameter for pastix solver")



class SolverOptionsParameters(DefaultSchema):
    degree = Int(
        required=False,
        default=1,
        missing=1,
        description="Degree of rquired transformation (0 - Rigid, 1 - Affine(default), 2 - Polynomial)")
    solver = Str(
        required=False,
        default="backslash",
        missing="backslash",
        description="type of solver to solve the system (default - backslash)")
    close_stack = Bool(
        required=False,
        default=False,
        description="whether the solver should close the stack after uploading results")
    transfac = Float(
        required=False,
        default=0.00001,
        missing=0.00001,
        description="translation factor")
    lambda_value = Float(
        required=False,
        default=1000,
        missing=1000,
        description="lambda for the solver")
    edge_lambda = Float(
        required=False,
        default=0.005,
        missing=0.005,
        description="edge lambda for solver regularization")
    nbrs = Int(
        required=False,
        default=2,
        missing=2,
        description="number of neighboring sections to consider (applies for cross section point matches)")
    nbrs_step = Int(
        required=False,
        default=1,
        missing=1,
        description="neighbors step")
    xs_weight = Float(
        required=True,
        description="Cross section point match weights")
    min_points = Int(
        required=False,
        default=5,
        missing=5,
        description="Minimum number of points correspondences required per tile pair")
    max_points = Int(
        required=False,
        default=200,
        missing=200,
        description="Maximum number of point correspondences required per tile pair")
    filter_point_matches = Int(
        required=False,
        default=1,
        missing=1,
        description="Filter point matches from collection (default = 1)")
    outlier_lambda = Int(
        required=False,
        default=1000,
        missing=1000,
        description="lambda value for outliers")
    min_tiles = Int(
        required=False,
        default=3,
        missing=3,
        description="Minimum number of tiles in section")
    Width = Int(
        required=True,
        description="Width of the tiles")
    Height = Int(
        required=True,
        description="Height of the tiles")
    outside_group = Int(
        required=False,
        default=0,
        missing=0,
        description="Outside group")
    matrix_only = Int(
        required=False,
        default=0,
        missing=0,
        description="matrix only")
    distribute_A = Int(
        required=False,
        default=16,
        missing=16,
        description="Distribute A matrix")
    dir_scratch = OutputDir(
        required=True,
        description="Scratch directory")
    distributed = Int(
        required=False,
        default=0,
        missing=0,
        description="Distributed parameter of solver")
    use_peg = Int(
        required=False,
        default=0,
        missing=0,
        description="Use pegs? (default = 0)")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="Verbose output from solver needed?")
    debug = Int(
        required=False,
        default=0,
        missing=0,
        description="turn on debug mode (default = 0 - off)")
    constrain_by_z = Int(
        required=False,
        default=0,
        missing=0,
        description="Constrain solution by z (default = 0)")
    sandwich = Int(
        required=False,
        default=0,
        missing=0,
        description="sandwich factor of solver")
    constraint_fac = Int(
        required=False,
        default=1e15,
        missing=1e15,
        description="Contraint factor")
    pmopts = Nested(
        PointMatchFilteringOptions,
        required=True,
        description="Point match filtering options for solver")
    pastix = Nested(
        PastixOptions,
        required=True,
        description="Pastix solver options")


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
    pass

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
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="Verbose output from point match loader needed?")


class SolveMontageSectionParameters(RenderParameters):
    first_section = Int(
        required=True,
        description="Z index of the first section")
    last_section = Int(
        required=True,
        description="Z index of the last section")
    clone_section_stack = Bool(
        required=False,
        default=True,
        description="Whether to clone out a temporary single section stack from source_collection stack")
    solver_executable = Str(
        required=True,
        description="Matlab solver executable with full path")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="Verbose output from solver needed?")
    solver_options = Nested(
        SolverOptionsParameters,
        required=True,
        description="Solver parameters")
    source_collection = Nested(
        SourceStackParameters,
        required=True,
        description="Input stack parameters, will be created and deleted after from input_stack")
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

        if data['source_collection']['owner'] is None:
            data['source_collection']['owner'] = data['render']['owner']
        if data['source_collection']['project'] is None:
            data['source_collection']['project'] = data['render']['project']
        if data['source_collection']['service_host'] is None:
            if data['render']['host'].find('http://') == 0:
                data['source_collection']['service_host'] = data['render']['host'][7:] + ":" + str(data['render']['port'])
            else:
                data['source_collection']['service_host'] = data['render']['host'] + ":" + str(data['render']['port'])
        if data['source_collection']['baseURL'] is None:
            data['source_collection']['baseURL'] = "http://{}:{}/render-ws/v1".format(data['render']['host'],data['render']['port']) 
        if data['source_collection']['renderbinPath'] is None:
            data['source_collection']['renderbinPath'] = data['render']['client_scripts']

        if data['target_collection']['owner'] is None:
            data['target_collection']['owner'] = data['render']['owner']
        if data['target_collection']['project'] is None:
            data['target_collection']['project'] = data['render']['project']
        if data['target_collection']['service_host'] is None:
            if data['render']['host'].find('http://') == 0:
                data['target_collection']['service_host'] = data['render']['host'][7:] + ":" + str(data['render']['port'])
            else:
                data['target_collection']['service_host'] = data['render']['host'] + ":" + str(data['render']['port'])
        if data['target_collection']['baseURL'] is None:
            data['target_collection']['baseURL'] = "http://{}:{}/render-ws/v1".format(data['render']['host'],data['render']['port']) 
        if data['target_collection']['renderbinPath'] is None:
            data['target_collection']['renderbinPath'] = data['render']['client_scripts']

        if data['source_point_match_collection']['server'] is None:
            data['source_point_match_collection']['server'] = data['source_collection']['baseURL']
        if data['source_point_match_collection']['owner'] is None:
            data['source_point_match_collection']['owner'] = data['render']['owner']

class SolverParameters(DefaultSchema):
    # NOTE: Khaled's EM_aligner needs some of the boolean variables as Integers
    # Hence providing the input as Integers
    degree = Int(
        required=True,
        default=1,
        description="Degree of transformation 1 - affine, "
                    "2 - second order polynomial, maximum is 3")
    solver = Str(
        required=False,
        default='backslash',
        missing='backslash',
        description="Solver type - default is backslash")
    transfac = Float(
        required=False,
        default=1e-15,
        missing=1e-15,
        description='Translational factor')
    lambda_value = Float(
        required=True,
        description="regularization parameter")
    edge_lambda = Float(
        required=True,
        description="edge lambda regularization parameter")
    nbrs = Int(
        required=False,
        default=3,
        missing=3,
        description="No. of neighbors")
    nbrs_step = Int(
        required=False,
        default=1,
        missing=1,
        description="Step value to increment the # of neighbors")
    xs_weight = Float(
        required=True,
        description="Weight ratio for cross section point matches")
    min_points = Int(
        required=True,
        default=8,
        description="Minimum no. of point matches per tile pair defaults to 8")
    max_points = Int(
        required=True,
        default=100,
        description="Maximum no. of point matches")
    filter_point_matches = Int(
        required=False,
        default=1,
        missing=1,
        description='set to a value 1 if point matches must be filtered')
    outlier_lambda = Float(
        required=True,
        default=100,
        description="Outlier lambda - large numbers result in "
                    "fewer tiles excluded")
    min_tiles = Int(
        required=False,
        default=2,
        missing=2,
        description="minimum number of tiles")
    Width = Int(
        required=False,
        default=3840,
        missing=3840,
        description='Width of the tiles (default = 3840)')
    Height = Int(
        required=False,
        default=3840,
        missing=3840,
        description='Height of the tiles (default= 3840)')
    outside_group = Int(
        required=False,
        default=0,
        missing=0,
        description='Outside group parameter (default = 0)')
    matrix_only = Int(
        required=False,
        default=0,
        missing=0,
        description="0 - solve (default), 1 - only generate "
                    "the matrix. For debugging only")
    distribute_A = Int(
        required=False,
        default=1,
        missing=1,
        description="Shards of A matrix")
    dir_scratch = InputDir(
        required=True,
        description="Scratch directory")
    distributed = Int(
        required=False,
        default=0,
        missing=0,
        description="distributed or not?")
    disableValidation = Int(
        required=False,
        default=1,
        missing=1,
        description="Disable validation while ingesting tiles?")
    use_peg = Int(
        required=False,
        default=0,
        missing=0,
        description="use pegs or not")
    complete = Int(
        required=False,
        default=0,
        missing=0,
        description="Set stack state to complete after processing?")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="want verbose output?")
    debug = Int(
        required=False,
        default=0,
        missing=0,
        description="Debug mode?")
    constrain_by_z = Int(
        required=False,
        default=0,
        missing=0,
        description='Contrain by z')
    sandwich = Int(
        required=False,
        default=0,
        missing=0,
        description='Sandwich parameter for solver')
    constraint_fac = Float(
        required=False,
        default=1e+15,
        missing=1e+15,
        description='Constraint factor')
    pmopts = Nested(
        PointMatchParameters,
        required=True,
        description='Point match filtering parameters')
    pastix = Nested(
        PastixParameters,
        required=False,
        default=None,
        missing=None,
        description="Pastix parameters if solving using Pastix")


class SolveRoughAlignmentParameters(RenderParameters):
    first_section = Int(
        required=True,
        description="Min Z value")
    last_section = Int(
        required=True,
        description="Max Z value")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description='Is verbose output required')
    source_collection = Nested(
        LowresStackParameters,
        required=True)
    target_collection = Nested(
        OutputLowresStackParameters,
        required=True)
    solver_options = Nested(
        SolverParameters,
        required=True)
    source_point_match_collection = Nested(
        PointMatchCollectionParameters,
        required=True)
    solver_executable = Str(
        required=True,
        description="Rough alignment solver executable file with full path")

    @post_load
    def add_missing_values(self, data):
        # cannot create "lambda" as a variable
        # name in SolverParameters. So, adding it here
        data['solver_options']['lambda'] = \
                data['solver_options']['lambda_value']
        data['solver_options'].pop('lambda_value', None)
        if data['solver_options']['pastix'] is None:
            data['solver_options'].pop('pastix', None)

        host = ""
        if data['render']['host'].find('http://') == 0:
            host = data['render']['host']
        else:
            host = "http://%s" % (data['render']['host'])

        if data['source_collection']['owner'] is None:
            data['source_collection']['owner'] = data['render']['owner']
        if data['source_collection']['project'] is None:
            data['source_collection']['project'] = data['render']['project']
        if data['source_collection']['service_host'] is None:
            if data['render']['host'].find('http://') == 0:
                data['source_collection']['service_host'] = (
                        data['render']['host'][7:] +
                        ":" + str(data['render']['port']))
            else:
                data['source_collection']['service_host'] = (
                        data['render']['host'] +
                        ":" + str(data['render']['port']))
        if data['source_collection']['baseURL'] is None:
            data['source_collection']['baseURL'] = (
                    host + ":" +
                    str(data['render']['port']) + '/render-ws/v1')
        if data['source_collection']['renderbinPath'] is None:
            data['source_collection']['renderbinPath'] = \
                    data['render']['client_scripts']

        if data['target_collection']['owner'] is None:
            data['target_collection']['owner'] = data['render']['owner']
        if data['target_collection']['project'] is None:
            data['target_collection']['project'] = data['render']['project']
        if data['target_collection']['service_host'] is None:
            if data['render']['host'].find('http://') == 0:
                data['target_collection']['service_host'] = (
                        data['render']['host'][7:] +
                        ":" + str(data['render']['port']))
            else:
                data['target_collection']['service_host'] = (
                        data['render']['host'] +
                        ":" + str(data['render']['port']))
        if data['target_collection']['baseURL'] is None:
            data['target_collection']['baseURL'] = (
                    host + ":" + str(data['render']['port']) + '/render-ws/v1')
        if data['target_collection']['renderbinPath'] is None:
            data['target_collection']['renderbinPath'] = \
                    data['render']['client_scripts']

        if data['source_point_match_collection']['server'] is None:
            data['source_point_match_collection']['server'] = \
                    data['source_collection']['baseURL']
        if data['source_point_match_collection']['owner'] is None:
            data['source_point_match_collection']['owner'] = \
                    data['render']['owner']

        # if solver is "pastix" then
        # data['solver_options']['pastix'] is required
        if data['solver_options']['solver'] is "pastix":
            pastix = data['solver_options']['pastix']
            if pastix['ncpus'] is None:
                data['solver_options']['pastix']['ncpus'] = 8
            if pastix['split'] is None:
                data['solver_options']['pastix']['split'] = 1
