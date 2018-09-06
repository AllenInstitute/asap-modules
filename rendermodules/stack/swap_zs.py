import renderapi
from rendermodules.module.render_module import RenderModule, RenderModuleException
from rendermodules.stack.schemas import SwapZsParameters, SwapZsOutput
import time

example = {
    "render": {
        "host": "em-131db",
        "port": 8080,
        "owner": "TEM",
        "project": "17797_1R",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts/"
    },
    "source_stack": "source_stack",
    "target_stack": "target_stack",
    "zValues": [],
    "delete_source_stack": "False"
}

class SwapZsModule(RenderModule):
    default_schema = SwapZsParameters
    default_output_schema = SwapZsOutput

    def swap_zs_from_stacks(self, source_stack, target_stack, zvalues):
        minz = min(zvalues)
        maxz = max(zvalues)
        # copy the section from target to a temp stack
        temp_stack = "em_2d_montage_solved_swap_temp_zs_{}_ze_{}_t{}".format(int(minz), int(maxz), time.strftime("%m%d%y_%H%M%S"))

        renderapi.stack.clone_stack(target_stack, temp_stack, zvalues, render=self.render)

        # set target stack in loading state
        renderapi.stack.set_stack_state(target_stack, state='LOADING', render=self.render)

        # delete those sections from the target stack
        for z in zvalues:
            renderapi.stack.delete_section(target_stack, z, render=self.render)
        
        # copy sections from source stack to target stack
        renderapi.stack.clone_stack(source_stack, target_stack, zs=zvalues, render=self.render)
        
        # set source stack in loading state
        renderapi.stack.set_stack_state(source_stack, state='LOADING', render=self.render)
        
        # delete those sections from source stack
        for z in zvalues:
            renderapi.stack.delete_section(source_stack, z, render=self.render)
        
        # copy sections from temp stack to source stack
        renderapi.stack.clone_stack(temp_stack, source_stack, zs=zvalues, render=self.render)

        if self.args['complete_source_stack']:
            renderapi.stack.set_stack_state(source_stack, state='COMPLETE', render=self.render)
        
        if self.args['complete_target_stack']:
            renderapi.stack.set_stack_state(target_stack, state='COMPLETE', render=self.render)

        # delete temp stack
        renderapi.stack.delete_stack(temp_stack, render=self.render)

        # delete source stack if specified in input
        if self.args['delete_source_stack']:
            renderapi.stack.delete_stack(source_stack, render=self.render)

        

    def run(self):
        if len(self.args['source_stack']) != len(self.args['target_stack']):
            raise RenderModuleException("Count of source and target stacks do not match")
        
        list_of_stacks = renderapi.render.get_stacks_by_owner_project(owner=self.render.DEFAULT_OWNER,
                                                                      project=self.render.DEFAULT_PROJECT,
                                                                      host=self.render.DEFAULT_HOST,
                                                                      port=self.render.DEFAULT_PORT,
                                                                      render=self.render)
        
        source_stacks = []
        target_stacks = []
        zvalues = []
        for source_stack, target_stack, zVals in zip(self.args['source_stack'], self.args['target_stack'], self.args['zValues']):
            if source_stack not in list_of_stacks or target_stack not in list_of_stacks:
                continue
            #if source_stack not in list_of_stacks:
            #    raise RenderModuleException("Source stack {} not in render".format(source_stack))
            
            #if target_stack not in list_of_stacks:
            #    raise RenderModuleException("Target stack {} not in render".format(target_stack))
            
            szvalues = renderapi.stack.get_z_values_for_stack(source_stack, render=self.render)
            tzvalues = renderapi.stack.get_z_values_for_stack(target_stack, render=self.render)
            avail_zs = set(szvalues).intersection(tzvalues)
            final_zs = list(set(zVals).intersection(avail_zs))

            source_stacks.append(source_stack)
            target_stacks.append(target_stack)
            zvalues.append(final_zs)

        self.swap_zs_from_stacks(source_stack, target_stack, final_zs)

        self.output({"source_stacks": source_stacks, "target_stacks": target_stacks, "zvalues": zvalues})

if __name__=="__main__":
    mod = SwapZsModule(input_data=example)
    mod.run()
