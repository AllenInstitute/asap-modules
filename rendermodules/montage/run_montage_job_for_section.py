import json
import os
import subprocess
import renderapi
import tempfile
from ..module.render_module import RenderModule, RenderModuleException
from rendermodules.montage.schemas import SolveMontageSectionParameters, SolveMontageSectionParametersOutput
from marshmallow import ValidationError
import time

try:
    xrange
except NameError:
    xrange = range

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.montage.run_montage_job_for_section"

# some parameters are repeated but required for Matlab solver to work

example = {
    "render": {
        "host": "ibs-forrestc-ux1",
        "port": 8988,
        "owner": "test",
        "project": "em_montage_test",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/dev/scripts/"
    },
    "first_section": 1015,
	"last_section": 1015,
	"solver_options": {
		"degree": 1,
		"solver": "backslash",
		"transfac": 1,
		"lambda": 0.005,
		"edge_lambda": 0.005,
		"nbrs": 2,
		"nbrs_step": 1,
		"xs_weight": 0,
		"min_points": 3,
		"max_points": 80,
		"filter_point_matches": 1,
		"outlier_lambda": 1000,
		"min_tiles": 3,
        "Width":3840,
        "Height":3840,
        "outside_group":0,
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
            "Transform":"Affine",
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
		"project": "em_montage_test",
		"stack": "input_raw_stack",
		"service_host": "ibs-forrestc-ux1:8988",
		"baseURL": "http://ibs-forrestc-ux1:8988/render-ws/v1",
		"renderbinPath": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/dev/scripts/",
		"verbose": 0
	},
	"target_collection": {
		"owner": "test",
		"project": "em_montage_test",
		"stack": "render_modules_test",
		"service_host": "ibs-forrestc-ux1:8988",
		"baseURL": "http://ibs-forrestc-ux1:8988/render-ws/v1",
		"renderbinPath": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/dev/scripts/",
		"verbose": 0
	},
	"source_point_match_collection": {
		"server": "http://ibs-forrestc-ux1:8988/render-ws/v1",
		"owner": "test",
		"match_collection": "test_montage_collection",
		"verbose": 0
	},
	"verbose": 0,
    "overwrite_z":"False",
    "swap_section":"True",
    "solver_executable": "/allen/aibs/pipeline/image_processing/volume_assembly/EMAligner/dev/allen_templates/run_em_solver.sh"
}

class SolveMontageSectionModule(RenderModule):
    default_schema = SolveMontageSectionParameters
    default_output_schema = SolveMontageSectionParametersOutput

    '''
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = SolveMontageSectionParameters
        super(SolveMontageSectionModule, self).__init__(
            schema_type=schema_type, *args, **kwargs)

        # EM_aligner doesn't like extra parameters in the input json file
        # Assigning the solver_executable to a different variable and removing it from args
        self.solver_executable = self.args['solver_executable']
        self.args.pop('solver_executable', None)
        self.clone_section_stack = self.args['clone_section_stack']
        self.args.pop('clone_section_stack')
        # if self.clone_section_stack:
        #     if (self.args['first_section']!=self.args['last_section']):
        #         raise ValidationError("first section and last section not equal")
    '''

    def run(self):
        if "MCRROOT" not in os.environ:
            raise ValidationError("MCRROOT not set")
        
        # EM_aligner doesn't like extra parameters in the input json file
        # Assigning the solver_executable to a different variable and removing it from args
        self.solver_executable = self.args['solver_executable']
        self.args.pop('solver_executable', None)
        self.clone_section_stack = self.args['clone_section_stack']
        self.args.pop('clone_section_stack')

        if self.clone_section_stack:
            tmp_stack = "{}_zs{}_ze{}_t{}".format(self.args['source_collection']['stack'],
                                           self.args['first_section'],
                                           self.args['last_section'],
                                           time.strftime("%m%d%y_%H%M%S"))
            zvalues = renderapi.stack.get_z_values_for_stack(self.args['source_collection']['stack'],render=self.render)
            zs = [z for z in zvalues if \
                (z>=self.args['first_section']) \
                and (z<=self.args['last_section'])]
            renderapi.stack.clone_stack(self.args['source_collection']['stack'],
                                        tmp_stack,
                                        zs=zs,
                                        close_stack=True,
                                        render=self.render)
            self.args['source_collection']['stack']=tmp_stack

            # the clone stack option should also set the first and last section z appropriately in self.args for solver
            self.args['first_section'] = min(zs)
            self.args['last_section'] = max(zs)

        # Check if the target stack exists and whether we need to overwrite the z
        target_host = self.args['target_collection']['service_host']
        num = target_host[-4:]
        port=None
        if num.isdigit():
            target_host = target_host[:-5]
            if target_host.find('http://') < 0:
                target_host = 'http://%s'%(target_host)
            port = int(num)

        list_of_stacks = renderapi.render.get_stacks_by_owner_project(owner=self.args['target_collection']['owner'],
                                                                      project=self.args['target_collection']['project'],
                                                                      host=target_host,
                                                                      port=port,
                                                                      render=self.render)

        backup_stack = self.args['target_collection']['stack']

        if self.args['target_collection']['stack'] in list_of_stacks: 
            # copt the sections into their own stack in case of reimaging
            for z in xrange(int(self.args['first_section']), int(self.args['last_section'])+1):
                if self.args['swap_section']:
                    temp_stack = "em_2d_montage_solved_backup_z_{}_t{}".format(z, time.strftime("%m%d%y_%H%M%S"))
        
                    renderapi.stack.clone_stack(self.args['target_collection']['stack'],
                                                temp_stack,
                                                zs=[z],
                                                render=self.render)
                    backup_stack = temp_stack
                    
                    renderapi.stack.delete_section(self.args['target_collection']['stack'],
                                                z,
                                                host=target_host,
                                                port=port,
                                                owner=self.args['target_collection']['owner'],
                                                project=self.args['target_collection']['project'],
                                                render=self.render)
                elif self.args['overwrite_z']:
                    renderapi.stack.delete_section(self.args['target_collection']['stack'],
                                                z,
                                                host=target_host,
                                                port=port,
                                                owner=self.args['target_collection']['owner'],
                                                project=self.args['target_collection']['project'],
                                                render=self.render)
                

        # generate a temporary json to feed in to the solver
        tempjson = tempfile.NamedTemporaryFile(
            suffix=".json",
            mode='w',
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

        #try to return the z's solved in the output json
        try:
            d={'zs':zs, 'backup_stack': backup_stack}
            self.output(d)
        except:
            raise RenderModuleException("unable to output json {}",d)

        #if you made a tmp stack destroy it
        if self.clone_section_stack:
            renderapi.stack.delete_stack(tmp_stack,render=self.render)


if __name__ == "__main__":
    mod = SolveMontageSectionModule(input_data=example)
    #module = SolveMontageSectionModule(schema_type=SolveMontageSectionParameters)
    mod.run()
