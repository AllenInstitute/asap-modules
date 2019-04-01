import renderapi
import json
from rendermodules.module.render_module import (
        StackTransitionModule, RenderModuleException)
from rendermodules.rough_align.schemas import (
        MakeAnchorStackSchema)


example = {
        "render": {
            "host": "em-131fs",
            "port": 8987,
            "owner": "TEM",
            "project": "17797_1R",
            "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
            },
        "transform_json": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/pre_align_rigid/manual_images/minnie_plus.json",
        "input_stack": "em_2d_montage_solved_py_0_01_mapped",
        "output_stack": "full_rough_anchor_stack_tmp",
        "close_stack": True
        }


class MakeAnchorStack(StackTransitionModule):
    default_schema = MakeAnchorStackSchema

    def run(self):
        with open(self.args['transform_json'], 'r') as f:
            tfj = json.load(f)
        keys = tfj.keys()

        new_specs = []
        for key in keys:
            z = int(key.split('_')[0])
            tilespec = renderapi.tilespec.get_tile_specs_from_z(
                    self.args['input_stack'],
                    z,
                    render=self.render)
            if len(tilespec) != 1:
                raise RenderModuleException(
                        "expected 1 tilespec for z = %d in stack %s, "
                        "found %d" %
                        (z, self.args['input_stack'], len(tilespec)))
            tilespec[0].tforms = [
                    renderapi.transform.AffineModel(json=tfj[key])]
            new_specs.append(tilespec[0])

        self.output_tilespecs_to_stack(new_specs)


if __name__ == "__main__":
    mmod = MakeAnchorStack(input_data=example, args=[])
    mmod.run()
