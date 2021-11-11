from argschema.fields import Int, Nested, Str
from marshmallow import post_load

from asap.module.render_module import RenderParameters
from asap.rough_align.schemas import (
    LowresStackParameters, OutputLowresStackParameters)
from asap.deprecated.solver.schemas import (
    SolverParameters, PointMatchCollectionParameters)


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
