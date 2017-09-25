import json
import os
import renderapi
from ..module.render_module import RenderModule, RenderParameters
import argschema
from argschema.fields import Bool, Float, Int, Nested, Str, InputFile
from argschema.schemas import DefaultSchema
import marshmallow as mm
from functools import partial
import numpy as np


if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.rough_align.do_rough_alignment"

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8998,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "lowres_stack": {
        "stack": "mm2_8bit_reimage_minimaps_not_scaled",
        "owner": "gayathri",
        "project": "MM2"
    },
    "output_lowres_stack": {
        "stack": "mm2_8bit_reimage_minimaps_not_scaled_rc",
        "owner": "gayathri",
        "project": "MM2"
    },
    "point_match_collection": {
        "owner": "gayathri_MM2",
        "collection": "mm2_8bit_reimage_minimaps_not_scaled",
        "scale": 0.4
    }
    "solver_options": {
        "min_tiles": 20,
        "degree": 1,
        "outlier_lambda": 100,
        "solver": "backslash",
        "matrix_only": 0,
        "distribute_A": 1,
        "dir_scratch": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch",
        "min_points": 20,
        "max_points": 100,
        "nbrs": 3,
        "xs_weight": 1,
        "stvec_flag": 1,
        "distributed": 0,
        "lambda": 1000,
        "edge_lambda": 1000,
        "use_peg": 0,
        "complete": 1,
        "disableValidation": 1,
        "apply_scaling": 1,
        "scale_fac": 20.0,
        "translation_only": 0,
        "translate_to_origin": 1,
        "verbose": 1,
        "debug": 0
    },
    "solver_executable":"/allen/aibs/shared/image_processing/volume_assembly/EM_aligner/matlab_compiled/do_rough_alignment",
    "minz": 1015,
    "maxz": 1118
}

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

class SolveRoughAlignmentModule(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = SolveRoughAlignmentParameters
        super(SolveRoughAlignmentModule, self).__init__(
            schema_type=schema_type, *args **kwargs)

        # Khaled's solver doesn't like extra parameters in the input json file
        # Assigning the solver_executable to a different variable and removing it from args
        self.solver_executable = self.args['solver_executable']
        self.args.pop('solver_executable', None)

    def run(self):
        # generate a temporary json to feed in to the solver
        tempjson = tempfile.NamedTemporaryFile(
            suffix=".json",
            mode="w",
            delete=False)
        tempjson.close()

        with open(tempjson.name, 'w') as f:
            json.dump(self.args, f, indent=4)
            f.close()

        # create the command to run
        # this code assumes that matlab environment is setup in the server for the user
        # add this to your profile
        # Note that MCRROOT is the matlab compiler runtime's root folder
        '''
            LD_LIBRARY_PATH=.:${MCRROOT}/runtime/glnxa64 ;
            LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${MCRROOT}/bin/glnxa64 ;
            LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${MCRROOT}/sys/os/glnxa64;
            LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${MCRROOT}/sys/opengl/lib/glnxa64;
        '''

        if os.path.isfile(self.solver_executable) and os.access(self.solver_executable, os.X_OK):
            cmd_to_qsub = "%s %s"%(self.solver_executable, tempjson.name)

        #generate pbs file
            temppbs = tempfile.NamedTemporaryFile(
                suffix=".pbs",
                mode="w",
                delete=False)
            temppbs.close()

            with open(temppbs.name, 'w') as f:
                f.write('#PBS -l mem=60g\n')
                f.write('#PBS -l walltime=00:00:20\n')
                f.write('#PBS -l ncpus=1\n')
                f.write('#PBS -N Montage\n')
                f.write('#PBS -r n\n')
                f.write('#PBS -m n\n')
                f.write('#PBS -q emconnectome\n')
                f.write('%s\n'%(cmd_to_qsub))
            f.close()

            qsub_cmd = 'qsub %s'%(temppbs.name)
            subprocess.call(qsub_cmd)

if __name__ == "__main__":
    mod = SolveRoughAlignmentModule(input_data=example)
    #module = SolveRoughAlignmentModule(schema_type=SolveMontageSectionParameters)
    mod.run()
