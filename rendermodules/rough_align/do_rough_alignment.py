import json
import os
import renderapi
import subprocess
from marshmallow import ValidationError
from functools import partial
import numpy as np
import tempfile
from ..module.render_module import RenderModule, RenderModuleException
from rendermodules.montage.schemas import SolveMontageSectionParameters


if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.rough_align.do_rough_alignment"

'''
example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "Tests",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "first_section": 1019,
	"last_section": 1023,
    "solver_options": {
		"degree": 1,
		"solver": "backslash",
		"transfac": 1e-15,
		"lambda": 100.0,
		"edge_lambda": 100.0,
		"nbrs": 5,
		"nbrs_step": 1,
		"xs_weight": 1,
		"min_points": 3,
		"max_points": 800,
		"filter_point_matches": 1,
		"outlier_lambda": 100,
		"min_tiles": 2,
        "Width":3840,
        "Height":3840,
        "outside_group":0,
        "close_stack":"True",
		"pastix": {
			"ncpus": 8,
			"parms_fn": "/nrs/flyTEM/khairy/FAFB00v13/matlab_production_scripts/params_file.txt",
			"split": 1
		},
		"matrix_only": 0,
		"distribute_A": 16,
		"dir_scratch": "/allen/aibs/pipeline/image_processing/volume_assembly/scratch/solver_scratch",
		"distributed": 0,
		"disableValidation": 1,
		"use_peg": 0,
		"pmopts": {
			"NumRandomSamplingsMethod": "Desired confidence",
			"MaximumRandomSamples": 5000,
			"DesiredConfidence": 99.9,
            "Transform":"AFFINE",
			"PixelDistanceThreshold": 0.1
		},
		"verbose": 1,
		"debug": 0,
		"constrain_by_z": 0,
		"sandwich": 0,
		"constraint_fac": 1e+15
	},
    "source_collection": {
		"owner": "gayathri",
		"project": "Tests",
		"stack": "rough_test_downsample_montage_stack",
		"service_host": "em-131fs:8080",
		"baseURL": "http://em-131fs:8080/render-ws/v1",
		"verbose": 0
	},
	"target_collection": {
		"owner": "gayathri",
		"project": "Tests",
		"stack": "rough_test_downsample_rough_stack",
		"service_host": "em-131fs:8080",
		"baseURL": "http://em-131fs:8080/render-ws/v1",
		"verbose": 0
	},
	"source_point_match_collection": {
		"server": "http://em-131fs:8080/render-ws/v1",
		"owner": "gayathri_MM2",
		"match_collection": "rough_test",
		"verbose": 0
	},
	"verbose": 0,
    "solver_executable": "/allen/aibs/pipeline/image_processing/volume_assembly/EMAligner/dev/allen_templates/run_em_solver.sh"
}
'''

example = {
    "render": {
        "host": "http://localhost",
        "port": 9000,
        "owner": "test",
        "project": "rough_align_test",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/staging/scripts/"
    },
    "first_section": 1020,
    "last_section": 1022,
    "solver_options": {
        "degree": 0,
    	"solver": "backslash",
    	"transfac": 1e-15,
    	"lambda": 100.0,
    	"edge_lambda": 100.0,
    	"nbrs": 5,
    	"nbrs_step": 1,
    	"xs_weight": 1,
    	"min_points": 3,
    	"max_points": 800,
    	"filter_point_matches": 1,
    	"outlier_lambda": 100,
    	"min_tiles": 2,
        "Width":3840,
        "Height":3840,
        "outside_group":0,
        "close_stack":"True",
    	"pastix": {
    		"ncpus": 8,
    		"parms_fn": "/nrs/flyTEM/khairy/FAFB00v13/matlab_production_scripts/params_file.txt",
    		"split": 1
    	},
    	"matrix_only": 0,
    	"distribute_A": 16,
    	"dir_scratch": "/allen/aibs/pipeline/image_processing/volume_assembly/scratch/solver_scratch",
    	"distributed": 0,
    	"disableValidation": 1,
    	"use_peg": 0,
    	"pmopts": {
    		"NumRandomSamplingsMethod": "Desired confidence",
    		"MaximumRandomSamples": 5000,
    		"DesiredConfidence": 99.9,
            "Transform":"AFFINE",
    		"PixelDistanceThreshold": 0.1
    	},
    	"verbose": 1,
    	"debug": 0,
    	"constrain_by_z": 0,
		"sandwich": 0,
		"constraint_fac": 1e+15
	},
    "source_collection": {
		"owner": "test",
		"project": "rough_align_test",
		"stack": "input_montage_stack_DS",
		"service_host": "localhost:9000",
		"baseURL": "http://localhost:9000/render-ws/v1",
		"verbose": 0
	},
	"target_collection": {
		"owner": "test",
		"project": "rough_align_test",
		"stack": "output_rough_DS",
		"service_host": "localhost:9000",
		"baseURL": "http://localhost:9000/render-ws/v1",
		"verbose": 0
	},
	"source_point_match_collection": {
		"server": "http://localhost:9000/render-ws/v1",
		"owner": "test",
		"match_collection": "rough_point_match_collection",
		"verbose": 0
	},
	"verbose": 0,
    "solver_executable": "/allen/aibs/pipeline/image_processing/volume_assembly/EMAligner/staging/allen_templates/run_em_solver.sh"
}


class SolveRoughAlignmentModule(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = SolveMontageSectionParameters
        super(SolveRoughAlignmentModule, self).__init__(
            schema_type=schema_type,
            *args,
            **kwargs)

        # Khaled's solver doesn't like extra parameters in the input json file
        # Assigning the solver_executable to a different variable and removing it from args
        self.solver_executable = self.args['solver_executable']
        self.args.pop('solver_executable', None)

    def run(self):
        if "MCRROOT" not in os.environ:
            raise ValidationError("MCRROOT not set")

        if self.args['first_section'] >= self.args['last_section']:
            raise RenderModuleException("First section z cannot be greater or equal to last section z")

        zvalues = renderapi.stack.get_z_values_for_stack(self.args['source_collection']['stack'], 
                                                         render=self.render)
        self.args['first_section'] = min(zvalues) if self.args['first_section'] > min(zvalues) else self.args['first_section']
        self.args['last_section'] = max(zvalues) if self.args['last_section'] > max(zvalues) else self.args['last_section']
        
        

        # generate a temporary json to feed in to the solver
        tempjson = tempfile.NamedTemporaryFile(
            suffix=".json",
            mode="w",
            delete=False)
        tempjson.close()

        with open(tempjson.name, 'w') as f:
            json.dump(self.args, f, indent=4)
            f.close()

        #assumes that solver_executable is the shell script that sets the LD_LIBRARY path and calls the executable
        cmd = "%s %s %s"%(self.solver_executable, os.environ['MCRROOT'],tempjson.name)
        ret = os.system(cmd)

        # on successful completion remove the input json file
        if ret == 0:
            os.remove(tempjson.name)
        else:
            raise RenderModuleException("solve failed with input_json {}",self.args)

        #try:
        #    d = {'minz':self.args['first_section'], 'maxz':self.args['last_section']}
        #    self.output(d)
        #except:
        #    raise RenderModuleException("unable to output json {}",d)


if __name__ == "__main__":
    mod = SolveRoughAlignmentModule(input_data=example)
    #module = SolveRoughAlignmentModule(schema_type=SolveMontageSectionParameters)
    mod.run()
