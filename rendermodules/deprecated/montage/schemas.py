from argschema.fields import Bool, Int, Nested, Str
from marshmallow import post_load

from rendermodules.module.render_module import RenderParameters
from rendermodules.deprecated.solver.schemas import (
    SolverOptionsParameters, SourceStackParameters, TargetStackParameters,
    PointMatchCollectionParameters)


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
