import json
import os
import renderapi
import subprocess
from ..module.render_module import RenderModule, RenderModuleException
from rendermodules.montage.schemas import SolveMontageSectionParameters
from marshmallow import ValidationError
from functools import partial
import numpy as np
import tempfile


if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.rough_align.do_rough_alignment"


example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "Tests",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "first_section": 1015,
	"last_section": 1020,
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
		"stack": "Secs_1015_1099_5_reflections_ds_montage",
		"service_host": "em-131fs:8080",
		"baseURL": "http://em-131fs:8080/render-ws/v1",
		"renderbinPath": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts",
		"verbose": 0
	},
	"target_collection": {
		"owner": "gayathri",
		"project": "Tests",
		"stack": "Secs_1015_1099_5_reflections_ds_rough_affine",
		"service_host": "em-131fs:8080",
		"baseURL": "http://em-131fs:8080/render-ws/v1",
		"renderbinPath": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts",
		"verbose": 0
	},
	"source_point_match_collection": {
		"server": "http://em-131fs:8080/render-ws/v1",
		"owner": "gayathri_MM2",
		"match_collection": "Secs_1015_1099_5_reflections_rough_test_pm",
		"verbose": 0
	},
	"verbose": 0,
    "solver_executable": "/allen/aibs/pipeline/image_processing/volume_assembly/EMAligner/dev/allen_templates/run_em_solver.sh"
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

        # one successful completion remove the input json file
        if ret == 0:
            os.remove(tempjson.name)
        else:
            raise RenderModuleException("solve failed with input_json {}",self.args)


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
        '''

if __name__ == "__main__":
    mod = SolveRoughAlignmentModule(input_data=example)
    #module = SolveRoughAlignmentModule(schema_type=SolveMontageSectionParameters)
    mod.run()
