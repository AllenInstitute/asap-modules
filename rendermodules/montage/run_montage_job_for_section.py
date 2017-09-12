import json
import os
import subprocess
from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
from marshmallow import Schema, validates_schema, post_load
import renderapi
from ..module.render_module import RenderModule, RenderParameters


if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.montage.generate_montage_input_json"

# some parameters are repeated but required for Matlab solver to work

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8998,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "solver_options": {
		"min_tiles": 3,
		"degree": 1,
		"outlier_lambda": 1000,
		"solver": "backslash",
		"min_points": 4,
		"max_points": 80,
		"stvec_flag": 0,
		"conn_comp": 1,
		"distributed": 0,
		"lambda": 1,
		"edge_lambda": 0.1,
		"small_region_lambda": 10,
		"small_region": 5,
		"calc_confidence": 1,
		"translation_fac": 1,
		"use_peg": 1,
		"peg_weight": 0.0001,
		"peg_npoints": 5
	},
    "source_collection": {
		"stack": "mm2_acquire_8bit",
		"owner": "gayathri",
		"project": "MM2",
		"service_host": "em-131fs:8998",
		"baseURL": "http://em-131fs:8998/render-ws/v1",
		"renderbinPath": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts",
		"verbose": 1
	},
    "target_collection": {
		"stack": "mm2_acquire_8bit_Montage",
		"owner": "gayathri",
		"project": "MM2",
		"service_host": "em-131fs:8998",
		"baseURL": "http://em-131fs:8998/render-ws/v1",
		"renderbinPath": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts",
		"verbose": 1,
		"initialize": 0,
		"complete": 1
	},
    "source_point_match_collection": {
		"server": "http://em-131fs:8998/render-ws/v1",
		"owner": "gayathri_MM2",
		"match_collection": "mm2_acquire_8bit_montage"
	},
    "z_value": 1049,
	"filter_point_matches": 1,
	"temp_dir": "/data/nc-em2/gayathrim/Janelia_Pipeline/scratch",
	"scratch": "/data/nc-em2/gayathrim/montage/scratch",
	"renderer_client": "/data/nc-em2/gayathrim/renderBin/bin/render.sh",
	"disableValidation": 1,
	"verbose": 1
}


class SolverParameters(DefaultSchema):
    min_tiles = Int(
        required=False,
        default=3,
        description="Minimum number of tiles in section")
    degree = Int(
        required=False,
        default=1,
        description="Degree of rquired transformation (0 - Rigid, 1 - Affine(default), 2 - Polynomial)")
    outlier_lambda = Int(
        required=False,
        default=1000,
        description="lambda value for outliers")
    solver = Str(
        required=False,
        default="backslash",
        description="type of solver to solve the system (default - backslash)")
    min_points = Int(
        required=False,
        default=4,
        description="Minimum number of points correspondences required per tile pair")
    max_points = Int(
        required=False,
        default=80,
        description="Maximum number of point correspondences required per tile pair")
    stvec_flag = Int(
        required=False,
        default=0,
        description="stvec flag for solver (default - 0)")
    conn_comp = Int(
        required=False,
        default=1,
        description="Connected components")
    distributed = Int(
        required=False,
        default=0,
        description="Distributed parameter of solver")
    lambda_value = Float(
        required=False,
        default=1,
        description="lambda for the solver")
    edge_lambda = Float(
        required=False,
        default=0.1,
        description="edge lambda for solver regularization")
    small_region_lambda = Float(
        required=False,
        default=10,
        description="small region lambda")
    small_region = Int(
        required=False,
        default=5,
        description="small region")
    calc_confidence = Int(
        required=False,
        default=1,
        description="Calculate confidence? (default = 1)")
    translation_fac = Int(
        required=False,
        default=1,
        description="translation factor")
    use_peg = Int(
        required=False,
        default=1,
        description="Use pegs? (default = 1)")
    peg_weight = Float(
        required=False,
        default=0.0001,
        description="Peg weight")
    peg_npoints = Int(
        required=False,
        default=5,
        description="Number of peg points")


class SourceStackParameters(DefaultSchema):
    stack = Str(
        required=True,
        description="Input source stack")
    owner = Str(
        required=False,
        default=None,
        description="Owner of the stack (defaults to render clients' owner)")
    project = Str(
        required=False,
        default=None,
        description="Project of the source stack")
    service_host = Str(
        required=False,
        default=None,
        description="url of render service host (without http://)")
    baseURL = Str(
        required=False,
        default=None,
        description="Base Render URL")
    renderbinPath = InputDir(
        required=False,
        default=None,
        description="Path to render's client scripts")
    verbose = Int(
        required=False,
        default=0,
        description="Verbose output from solver needed?")


class TargetStackParameters(DefaultSchema):
    stack = Str(
        required=True,
        description="Output montage stack")
    owner = Str(
        required=False,
        default=None,
        description="Owner of the stack (defaults to render clients' owner)")
    project = Str(
        required=False,
        default=None,
        description="Project of the target stack")
    service_host = Str(
        required=False,
        default=None,
        description="url of render service host (without http://)")
    baseURL = Str(
        required=False,
        default=None,
        description="Base Render URL")
    renderbinPath = InputDir(
        required=False,
        default=None,
        description="Path to render's client scripts")
    verbose = Int(
        required=False,
        default=0,
        description="Verbose output from solver needed?")
    initialize = Int(
        required=False,
        default=0,
        description="Do you want to initialize the stack from scratch")


class PointMatchCollectionParameters(DefaultSchema):
    server = Str(
        required=False,
        default=None,
        description="Render server's base URL")
    owner = Str(
        required=False,
        default=None,
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
        description="Do you want to filter point matches? default - 1")
    temp_dir = InputDir(
        required=True,
        default="/allen/aibs/shared/image_processing/volume_assembly/scratch")
    scratch = InputDir(
        required=True,
        default="/allen/aibs/shared/image_processing/volume_assembly/scratch")
    renderer_client = Str(
        required=False,
        default=None,
        description="Path to render client script render.sh")
    solver_options = Nested(
        SolverParameters,
        required=True)
    source_collection = Nested(
        SourceStackParameters,
        required=True)
    target_collection = Nested(
        TargetStackParameters,
        required=True)
    source_point_match_collection = Nested(
        PointMatchCollectionParameters,
        required=True)

    @post_load()
    def add_missing_values(self, data):
        # cannot create "lambda" as a variable name in SolverParameters
        data['solver_options']['lambda'] = data['solver_options']['lambda_value']

    @validates_schema()
    def validate_data(self, data):
        if data['source_collection']['owner'] is None:
            data['source_collection']['owner'] = self.args['render']['owner']
        if data['source_collection']['project'] is None:
            data['source_collection']['project'] = self.args['render']['project']
        if data['source_collection']['service_host'] is None:
            data['source_collection']['service_host'] = self.args['render']['host'][7:] + ":" + str(self.args['render']['port'])
        if data['source_collection']['baseURL'] is None:
            data['source_collection']['baseURL'] = self.args['render']['host'] + ":" + str(self.args['render']['port']) + '/render-ws/v1'
        if data['source_collection']['renderbinPath'] is None:
            data['source_collection']['renderbinPath'] = self.args['render']['client_scripts']

        if data['target_collection']['owner'] is None:
            data['target_collection']['owner'] = self.args['render']['owner']
        if data['target_collection']['project'] is None:
            data['target_collection']['project'] = self.args['render']['project']
        if data['target_collection']['service_host'] is None:
            data['target_collection']['service_host'] = self.args['render']['host'][7:] + ":" + str(self.args['render']['port'])
        if data['target_collection']['baseURL'] is None:
            data['target_collection']['baseURL'] = self.args['render']['host'] + ":" + str(self.args['render']['port']) + '/render-ws/v1'
        if data['target_collection']['renderbinPath'] is None:
            data['target_collection']['renderbinPath'] = self.args['render']['client_scripts']

        if data['source_point_match_collection']['server'] is None:
            data['source_point_match_collection']['server'] = data['source_collection']['baseURL']
        if data['source_point_match_collection']['owner'] is None:
            data['source_point_match_collection']['owner'] = self.args['render']['owner']
        
