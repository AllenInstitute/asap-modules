import json
import os
import renderapi
from ..module.render_module import RenderModule
from rendermodules.rough_align.schemas import SolveRoughAlignmentParameters
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
        "stack": "mm2_8bit_reimage_minimaps",
        "owner": "gayathri",
        "project": "MM2"
    },
    "output_lowres_stack": {
        "stack": "mm2_8bit_reimage_minimaps",
        "owner": "gayathri",
        "project": "MM2"
    },
    "point_match_collection": {
        "owner": "gayathri_MM2",
        "collection": "mm2_8bit_reimage_minimaps",
        "scale": 0.4
    },
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
