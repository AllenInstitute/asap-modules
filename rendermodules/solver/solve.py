import argschema
import renderapi
import time
from EMaligner import EMaligner

from rendermodules.solver.schemas import EMA_Input_Schema, EMA_Output_Schema

montage_example = {
   "first_section": 1020,
   "last_section": 1020,
   "solve_type": "montage",
   "close_stack": "True",
   "transformation": "affine",
   "start_from_file": "",
   "output_mode": "stack",
   "input_stack": {
       "owner": "gayathri",
       "project": "MM2",
       "name": "mm2_acquire_8bit_reimage_postVOXA_TEMCA2_rev1039",
       "host": "em-131fs",
       "port": 8080,
       "mongo_host": "em-131fs",
       "mongo_port": 27017,
       "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
       "collection_type": "stack",
       "db_interface": "mongo"
   },
   "pointmatch": {
       "owner": "gayathri_MM2",
       "name": "mm2_acquire_8bit_reimage_postVOXA_TEMCA2_Fine_rev1039",
       "host": "em-131fs",
       "port": 8080,
       "mongo_host": "em-131fs",
       "mongo_port": 27017,
       "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
       "collection_type": "pointmatch",
       "db_interface": "mongo"
   },
   "output_stack": {
       "owner": "danielk",
       "project": "Tests",
       "name": "python_montage_results",
       "host": "em-131fs",
       "port": 8080,
       "mongo_host": "em-131fs",
       "mongo_port": 27017,
       "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
       "collection_type": "stack",
       "db_interface": "render"
   },
   "hdf5_options": {
       "output_dir": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/example_output/",
       "chunks_per_file": -1
   },
   "matrix_assembly": {
       "depth": 2,
       "montage_pt_weight": 1.0,
       "cross_pt_weight": 0.5,
       "npts_min": 5,
       "npts_max": 500,
       "inverse_dz":"True"
   },
   "regularization": {
       "default_lambda": 1.0e3,
       "translation_factor": 1.0e-5
   },
   "clone_section": "False",
   "overwrite_z": "True"
}


class Solve_stack(argschema.ArgSchemaParser):
    default_schema = EMA_Input_Schema
    default_output_schema = EMA_Output_Schema

    def run(self):
        render = renderapi.connect(**self.args['output_stack'])

        list_of_stacks = renderapi.render.get_stacks_by_owner_project(host=render.DEFAULT_HOST,
                                                                      port=render.DEFAULT_PORT,
                                                                      owner=render.DEFAULT_OWNER,
                                                                      project=render.DEFAULT_PROJECT,
                                                                      render=render)
        
        backup_stack = []

        if self.args['output_stack']['name'] in list_of_stacks:
            for z in xrange(self.args['first_section'], self.args['last_section']+1):
                renderapi.stack.set_stack_state(self.args['output_stack']['name'], 'LOADING', render=render)
                    
                if self.args['clone_section']:
                    temp_stack = "em_2d_montage_solved_backup_z_{}_t{}".format(int(z), time.strftime("%m%d%y_%H%M%S"))

                    renderapi.stack.clone_stack(self.args['output_stack']['name'],
                                                temp_stack,
                                                zs=[z],
                                                render=render)
                    backup_stack.append(temp_stack)
                    
                    renderapi.stack.delete_section(self.args['output_stack']['name'],
                                                   z,
                                                   host=render.DEFAULT_HOST,
                                                   port=render.DEFAULT_PORT,
                                                   owner=render.DEFAULT_OWNER,
                                                   project=render.DEFAULT_PROJECT,
                                                   render=render)
                elif self.args['overwrite_z']:
                    #renderapi.stack.set_stack_state(self.args['output_stack']['name'], 'LOADING', render=render)
                    renderapi.stack.delete_section(self.args['output_stack']['name'],
                                                   z,
                                                   host=render.DEFAULT_HOST,
                                                   port=render.DEFAULT_PORT,
                                                   owner=render.DEFAULT_OWNER,
                                                   project=render.DEFAULT_PROJECT,
                                                   render=render)
        
        if not backup_stack:
            backup_stack.append(self.args['output_stack']['name'])

        
        self.module = EMaligner.EMaligner(input_data=self.args, args=[])
        self.module.run()
        self.output(
            {"stack": self.args['output_stack']['name'], "backup_stack": backup_stack})


if __name__ == "__main__":
    module = Solve_stack(input_data=montage_example)
    module.run()
