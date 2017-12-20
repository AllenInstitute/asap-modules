import json
import os
import subprocess
import renderapi
import tempfile
from ..module.render_module import RenderModule, RenderModuleException
from rendermodules.montage.schemas import SolveMontageSectionParameters


if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.montage.run_montage_job_for_section"

# some parameters are repeated but required for Matlab solver to work

example = {
    "render": {
        "host": "http://ibs-forrestc-ux1",
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
		"match_collection": "test_collection",
		"verbose": 0
	},
	"verbose": 0,
    "solver_executable": "/allen/aibs/pipeline/image_processing/volume_assembly/EMAligner/dev/allen_templates/em_solver"
}

'''
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
		"lambda_value": 1,
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
		"verbose": 0
	},
    "target_collection": {
		"stack": "mm2_acquire_8bit_Montage",
        "owner": "gayathri",
		"project": "MM2",
		"service_host": "em-131fs:8998",
		"baseURL": "http://em-131fs:8998/render-ws/v1",
		"renderbinPath": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts",
		"verbose": 0,
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
    "solver_executable": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/EM_aligner/matlab_compiled/solve_montage_SL",
	"temp_dir": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch",
	"dir_scratch": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch",
	"renderer_client": "/data/nc-em2/gayathrim/renderBin/bin/render.sh",
	"disableValidation": 1,
	"verbose": 0
}
'''

class SolveMontageSectionModule(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = SolveMontageSectionParameters
        super(SolveMontageSectionModule, self).__init__(
            schema_type=schema_type, *args, **kwargs)

        # EM_aligner doesn't like extra parameters in the input json file
        # Assigning the solver_executable to a different variable and removing it from args
        self.solver_executable = self.args['solver_executable']
        self.args.pop('solver_executable', None)

    def run(self):
        # generate a temporary json to feed in to the solver
        tempjson = tempfile.NamedTemporaryFile(
            suffix=".json",
            mode='w',
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

        if "MCRROOT" not in os.environ:
            raise ValidationError("MCRROOT not set")
        
        os.environ['LD_LIBRARY_PATH']=''
        mcrroot = os.environ['MCRROOT']
        path1 = os.path.join(mcrroot, 'runtime/glnxa64')
        path2 = os.path.join(mcrroot, 'bin/glnxa64')
        path3 = os.path.join(mcrroot, 'sys/os/glnxa64')
        path4 = os.path.join(mcrroot, 'sys/opengl/lib/glnxa64')
        
        os.environ['LD_LIBRARY_PATH'] += path1 + os.pathsep
        os.environ['LD_LIBRARY_PATH'] += path2 + os.pathsep
        os.environ['LD_LIBRARY_PATH'] += path3 + os.pathsep
        os.environ['LD_LIBRARY_PATH'] += path4 + os.pathsep
                
        cmd = "%s %s"%(self.solver_executable, tempjson.name)
        ret = os.system(cmd)

        # one successful completion remove the input json file
        if ret == 0:
            os.remove(tempjson.name)
        else:
            raise RenderModuleException("solve failed with input_json {}",self.args)

        sectionDataList = renderapi.stack.get_stack_sectionData(self.args['target_collection']['stack'],
            render=self.render)
        sectionData = next(section for section in sectionDataList if section['first_section']==self.args['z_value'])
        self.output(sectionData)

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
                f.write('#PBS -l walltime=00:30:00\n')
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
    mod = SolveMontageSectionModule(input_data=example)
    #module = SolveMontageSectionModule(schema_type=SolveMontageSectionParameters)
    mod.run()
