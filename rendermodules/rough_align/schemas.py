from argschema import InputFile, InputDir
import marshmallow as mm
from argschema.fields import Bool, Float, Int, Nested, Str, InputFile
from argschema.schemas import DefaultSchema
import argschema




class ApplyRoughAlignmentTransformParameters(RenderParameters):
    montage_stack = mm.fields.Str(
        required=True,
        metadata={'description':'stack to make a downsample version of'})
    prealigned_stack = mm.fields.Str(
        required=False,
        default=None,
        missing=None,
        metadata={'description':'stack with dropped tiles corrected for stitching errors'})
    lowres_stack = mm.fields.Str(
        required=True,
        metadata={'description':'montage scape stack with rough aligned transform'})
    output_stack = mm.fields.Str(
        required=True,
        metadata={'description':'output high resolution rough aligned stack'})
    tilespec_directory = mm.fields.Str(
        required=True,
        metadata={'description':'path to save section images'})
    set_new_z = mm.fields.Boolean(
        required=False,
        default=False,
        missing=False,
        metadata={'description':'set to assign new z values starting from 0 (default - False)'})
    consolidate_transforms = mm.fields.Boolean(
        required=False,
        default=True,
        missing=True,
        metadata={'description':'should the transforms be consolidated? (default - True)'})
    scale = mm.fields.Float(
        required=True,
        metadata={'description':'scale of montage scapes'})
    pool_size = mm.fields.Int(
        require=False,
        default=10,
        missing=10,
        metadata={'description':'pool size for parallel processing'})
    minZ = mm.fields.Int(
        required=True,
        metadata={'description':'Minimum Z value'})
    maxZ = mm.fields.Int(
        required=True,
        metadata={'description':'Maximum Z value'})

    @validates_schema()
    def validate_data(self, data):
        if data['prealigned_stack'] is None:
            data['prealigned_stack'] = data['montage_stack']


class LowresStackParameters(DefaultSchema):
    stack = Str(
        required=True,
        description="Input downsample images section stack")
    owner = Str(
        required=False,
        missing=None,
        description="Owner of the input lowres stack")
    project = Str(
        required=False,
        missing=None,
        description="Project of the input lowres stack")
    service_host = Str(
        required=False,
        missing=None,
        description="Service host for the input stack Render service")
    baseURL = Str(
        required=False,
        missing=None,
        description="Base URL of the Render service for the source stack")
    renderbinPath = Str(
        required=False,
        missing=None,
        description="Client scripts location")
    verbose = Int(
        required=False,
        default=0,
        description="Want the output to be verbose?")

class OutputLowresStackParameters(DefaultSchema):
    stack = Str(
        required=True,
        description="Input downsample images section stack")
    owner = Str(
        required=False,
        missing=None,
        description="Owner of the input lowres stack")
    project = Str(
        required=False,
        missing=None,
        description="Project of the input lowres stack")
    service_host = Str(
        required=False,
        missing=None,
        description="Service host for the input stack Render service")
    baseURL = Str(
        required=False,
        missing=None,
        description="Base URL of the Render service for the source stack")
    renderbinPath = Str(
        required=False,
        missing=None,
        description="Client scripts location")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="Want the output to be verbose?")

class PointMatchCollectionParameters(DefaultSchema):
    owner = Str(
        required=True,
        description="Point match collection owner")
    collection = Str(
        required=True,
        description="Point match collection name")
    scale = Float(
        required=True,
        description="Scale at which the point matches were generated (different from the scale of the downsample section images)")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="Verbose output flag")

class PastixParameters(DefaultSchema):
    ncpus = Int(
        required=False,
        default=8,
        missing=8,
        description="No. of cpu cores. Default = 8")
    parms_fn = InputFile(
        required=False,
        default=None,
        missing=None,
        description="Path to parameters pastix parameters file")
    split = Int(
        required=False,
        default=1,
        missing=1,
        description="set to either 0 (no split) or 1 (split)")


class SolverParameters(DefaultSchema):
    # NOTE: Khaled's EM_aligner needs some of the boolean variables as Integers
    # Hence providing the input as Integers
    min_tiles = Int(
        required=False,
        default=20,
        missing=20,
        description="minimum number of tiles")
    degree = Int(
        required=True,
        default=1,
        description="Degree of transformation 1 - affine, 2 - second order polynomial, maximum is 3")
    outlier_lambda = Float(
        required=True,
        default=100,
        description="Outlier lambda - large numbers result in fewer tiles excluded")
    solver = Str(
        required=False,
        default='backslash',
        missing='backslash',
        description="Solver type - default is backslash")
    matrix_only = Int(
        required=False,
        default=0,
        missing=0,
        description="0 - solve (default), 1 - only generate the matrix. For debugging only")
    distribute_A = Int(
        required=False,
        default=1,
        missing=1,
        description="Shards of A matrix")
    dir_scratch = InputDir(
        required=True,
        description="Scratch directory")
    min_points = Int(
        required=True,
        default=8,
        description="Minimum no. of point matches per tile pair defaults to 8")
    max_points = Int(
        required=True,
        default=100,
        description="Maximum no. of point matches")
    nbrs = Int(
        required=True,
        default=4,
        missing=4,
        description="No. of neighbors")
    xs_weight = Float(
        required=True,
        description="Weight ratio for cross section point matches")
    stvec_flag = Int(
        required=False,
        default=1,
        missing=1,
        description="0 - regularization against rigid model (i.e. starting value is not supplied by rc)")
    distributed = Int(
        required=False,
        default=0,
        missing=0,
        description="distributed or not?")
    lambdas = Float(
        required=True,
        description="regularization parameter")
    edge_lambda = Float(
        required=True,
        description="edge lambda regularization parameter")
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
    disableValidation = Int(
        required=False,
        default=1,
        missing=1,
        description="Disable validation while ingesting tiles?")
    apply_scaling = Int(
        required=False,
        default=1,
        missing=1,
        description="Apply scaling?")
    translation_only = Int(
        required=False,
        default=1,
        missing=1,
        description="Translation only parameter")
    translate_to_origin = Int(
        required=False,
        default=1,
        missing=1,
        description="Translate sections to origin")
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
    pstix = Nested(
        PastixParameters,
        required=False)

class SolveRoughAlignmentParameters(RenderParameters):
    minz = Int(
        required=True,
        description="Min Z value")
    maxz = Int(
        required=True,
        description="Max Z value")
    lowres_stack_parameters = Nested(
        LowresStackParameters,
        required=True)
    output_stack_parameters = Nested(
        OutputLowresStackParameters,
        required=True)
    solver_options = Nested(
        SolverParameters,
        required=True)
    point_match_collection = Nested(
        PointMatchCollectionParameters,
        required=True)
    solver_executable = Str(
        required=True,
        description="Rough alignment solver executable file with full path")

    @post_load()
    def add_missing_values(self, data):
        # cannot create "lambda" as a variable name in SolverParameters. So, adding it here
        data['solver_options']['lambda'] = data['solver_options']['lambdas']
        data['solver_options'].pop('lambdas', None)

    @validates_schema()
    def validate_data(self, data):
        if data['lowres_stack_parameters']['owner'] is None:
            data['lowres_stack_parameters']['owner'] = data['render']['owner']
        if data['lowres_stack_parameters']['project'] is None:
            data['lowres_stack_parameters']['project'] = data['render']['project']
        if data['lowres_stack_parameters']['service_host'] is None:
            data['lowres_stack_parameters']['service_host'] = data['render']['host'][7:] + ":" + str(data['render']['port'])
        if data['lowres_stack_parameters']['baseURL'] is None:
            data['lowres_stack_parameters']['baseURL'] = data['render']['host'] + ":" + str(data['render']['port']) + '/render-ws/v1'
        if data['lowres_stack_parameters']['renderbinPath'] is None:
            data['lowres_stack_parameters']['renderbinPath'] = data['render']['client_scripts']

        if data['output_stack_parameters']['owner'] is None:
            data['output_stack_parameters']['owner'] = data['render']['owner']
        if data['output_stack_parameters']['project'] is None:
            data['output_stack_parameters']['project'] = data['render']['project']
        if data['output_stack_parameters']['service_host'] is None:
            data['output_stack_parameters']['service_host'] = data['render']['host'][7:] + ":" + str(data['render']['port'])
        if data['output_stack_parameters']['baseURL'] is None:
            data['output_stack_parameters']['baseURL'] = data['render']['host'] + ":" + str(data['render']['port']) + '/render-ws/v1'
        if data['output_stack_parameters']['renderbinPath'] is None:
            data['output_stack_parameters']['renderbinPath'] = data['render']['client_scripts']

        if data['point_match_collection']['server'] is None:
            data['point_match_collection']['server'] = data['render']['owner']
        if data['point_match_collection']['owner'] is None:
            data['point_match_collection']['owner'] = data['render']['owner']
