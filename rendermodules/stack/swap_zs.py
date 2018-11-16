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

def delete_temp_stacks(render, temp_stack_list):
    for temps in temp_stack_list:
        try:
            renderapi.stack.delete_stack(temps, render=render)
        except Exception as e:
            print("Could not delete stack {}".format(temps))


def swap_section(render, source_stack, target_stack, z, pool_size=5):
    session = requests.Session()
    session.mount('http://', requests.adapters.HTTPAdapter(max_retries=5))

    source_ts = renderapi.resolvedtiles.get_resolved_tiles_from_z(source_stack, z, render=render)
    target_ts = renderapi.resolvedtiles.get_resolved_tiles_from_z(target_stack, z, render=render)

    source_tileids = [ts.tileId for ts in source_ts.tilespecs]
    target_tileids = [ts.tileId for ts in target_ts.tilespecs]

    if set(source_tileids) == set(target_tileids):
        print("{} and {} stack have same tileIds for Z = {}".format(source_stack, target_stack, z))
        return False

    # write these tilespecs to the appropriate stacks
    try:
        renderapi.stack.set_stack_state(source_stack, "LOADING", render=render)
        render.run(renderapi.client.import_tilespecs_parallel,
                   source_stack,
                   target_ts.tilespecs,
                   sharedTransforms=target_ts.transforms,
                   poolsize=pool_size,
                   close_stack=False)
    except Exception as e:
        print("Cannot import tilespecs to {} from {}".format(source_stack, target_stack))
        return False

    try:
        renderapi.stack.set_stack_state(target_stack, "LOADING", render=render)
        render.run(renderapi.client.import_tilespecs_parallel,
                   target_stack,
                   source_ts.tilespecs,
                   sharedTransforms=source_ts.transforms,
                   poolsize=pool_size,
                   close_stack=False)
    except Exception as e:
        print("Cannot import tilespecs to {} from {}".format(target_stack, source_stack))
        return False
    
    try:
        for ts in source_ts.tilespecs:
            renderapi.stack.delete_tile(source_stack, ts.tileId, session=session, render=render)
    except Exception as e:
        print("Cannot delete old tile ids from {}, error: e".format(source_stack, e))
    
    try:
        for ts in target_ts.tilespecs:
            renderapi.stack.delete_tile(target_stack, ts.tileId, session=session, render=render)
    except Exception as e:
        print("Cannot delete old tile ids from {}, error: e".format(target_stack, e))
    
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

            #source_stacks.append(source_stack)
            #target_stacks.append(target_stack)
            #zvalues.append(final_zs)
            print(final_zs)
            #mypartial = partial(swap_section, self.render, source_stack, target_stack)

            #with renderapi.client.WithPool(self.args['pool_size']) as pool:
            #    output_bool = pool.map(mypartial, final_zs)
        
            output_bool = []
            for z in final_zs:
                outbool = swap_section(self.render, source_stack, target_stack, z)
                output_bool.append(outbool)

            for z, n in zip(final_zs, output_bool):
                if n:
                    zvalues.append(z)
                    source_stacks.append(source_stack)
                    target_stacks.append(target_stack)

            #zs = [z for z, n in zip(final_zs, output_bool) if n]
            #zvalues.append(zs)
            

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
