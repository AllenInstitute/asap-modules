import renderapi
from rendermodules.module.render_module import RenderModule, RenderModuleException
from rendermodules.stack.schemas import SwapZsParameters, SwapZsOutput
import time
import requests
from functools import partial

example = {
    "render": {
        "host": "em-131db",
        "port": 8080,
        "owner": "gayathrim",
        "project": "17797_1R",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts/"
    },
    "source_stack": "source_stack",
    "target_stack": "target_stack",
    "zValues": [[1015]],
    "delete_source_stack": "False"
}

def swap_section(render, source_stack, target_stack, z):
    session = requests.Session()
    session.mount('http://', requests.adapters.HTTPAdapter(max_retries=5))

    source_ts = renderapi.resolvedtiles.get_resolved_tiles_from_z(source_stack, z, render=render)
    target_ts = renderapi.resolvedtiles.get_resolved_tiles_from_z(target_stack, z, render=render)

    temp_stacks = []
    # write the tilespecs to a temp stack
    temp_stack1 = "em_2d_montage_solved_swap_temp_stack_{}_z{}_t{}".format(source_stack, z, time.strftime("%m%d%y_%H%M%S"))
    temp_stack2 = "em_2d_montage_solved_swap_temp_stack_{}_z{}_t{}".format(target_stack, z, time.strftime("%m%d%y_%H%M%S"))

    try:
        render.run(renderapi.client.import_tilespecs_parallel,
                        temp_stack1,
                        source_ts.tilespecs,
                        sharedTransforms=source_ts.transforms)
    except Exception as e:
        print("Could not import tilespecs to {}".format(temp_stack1))
        return False
    
    try:
        render.run(renderapi.client.import_tilespecs_parallel,
                        temp_stack2,
                        target_ts.tilespecs,
                        sharedTransforms=target_ts.transforms)
    except Exception as e:
        print("Could not import tilespecs to {}".format(temp_stack2))
        return False
    
    temp_stacks = [temp_stack1, temp_stack2]

    # delete the section from source and target stacks now
    try:
        response = renderapi.stack.delete_section(target_stack, z, render=render, session=session)
    except Exception as e:
        print("Cannot delete section {} from {}".format(z, target_stack))
        return False
    
    try:
        response = renderapi.stack.delete_section(source_stack, z, render=render, session=session)
    except Exception as e:
        print("Cannot delete section {} from {}".format(z, source_stack))
        # restore the section in target_stack
        render.run(renderapi.client.import_tilespecs_parallel,
                        target_stack,
                        target_ts.tilespecs,
                        sharedTransforms=target_ts.transforms,
                        session=session)
        return False
    
    # both stacks do not have the section now

    try:
        render.run(renderapi.stack.set_stack_state,
                        source_stack,
                        "LOADING",
                        session=session)
        render.run(renderapi.client.import_tilespecs_parallel,
                        source_stack,
                        target_ts.tilespecs,
                        sharedTransforms=target_ts.transforms)
    except Exception as e:
        print("Cannot import tilespecs to {} from {}".format(source_stack, target_stack))
        return False
    
    try:
        render.run(renderapi.stack.set_stack_state,
                        target_stack,
                        "LOADING",
                        session=session)
        render.run(renderapi.client.import_tilespecs_parallel,
                        target_stack,
                        source_ts.tilespecs,
                        sharedTransforms=source_ts.transforms)
    except Exception as e:
        print("Cannot import tilespecs to {} from {}".format(target_stack, source_stack))
        return False
    
    # delete temp stacks
    try:
        for t in temp_stacks:
            render.run(renderapi.stack.delete_stack, t)
    except Exception as e:
        print("Cannot delete temp stacks {}".format(temp_stacks))
    
    return True
        


class SwapZsModule(RenderModule):
    default_schema = SwapZsParameters
    default_output_schema = SwapZsOutput

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
            if source_stack not in list_of_stacks or target_stack not in list_of_stacks: # pragma: no cover
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
            #zvalues.append(final_zs)
            print(final_zs)
            mypartial = partial(swap_section, self.render, source_stack, target_stack)

            with renderapi.client.WithPool(self.args['pool_size']) as pool:
                output_bool = pool.map(mypartial, final_zs)

            zs = [z for z, n in zip(final_zs, output_bool) if n]
            zvalues.append(zs)

            if self.args['complete_source_stack']:
                renderapi.stack.set_stack_state(source_stack, state='COMPLETE', render=self.render)
        
            if self.args['complete_target_stack']:
                renderapi.stack.set_stack_state(target_stack, state='COMPLETE', render=self.render)

            # delete source stack if specified in input
            if self.args['delete_source_stack']: # pragma: no cover
                renderapi.stack.delete_stack(source_stack, render=self.render)

            #self.swap_zs_from_stacks(source_stack, target_stack, final_zs)

        self.output({"source_stacks": source_stacks, "target_stacks": target_stacks, "swapped_zvalues": zvalues})

if __name__ == "__main__":
    mod = SwapZsModule(input_data=example)
    mod.run()
