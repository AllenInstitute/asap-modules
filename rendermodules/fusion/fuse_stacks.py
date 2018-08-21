#!/usr/bin/env python
'''
fuse overlapping render stacks registered by an Affine Homography transform
    similar to Parallel Elastic Alignment
'''
import copy
import os

import renderapi
from six import viewkeys

from ..module.render_module import RenderModule
from .schemas import FuseStacksParameters, FuseStacksOutput

example_parameters = {
    "render": {
        "host": "em-131fs",
        "port": 8080,
        "owner": "testuser",
        "project": "test",
        "client_scripts": ""
    },
    "stacks": {
        "stack": "PARENTSTACK",
        "transform": {
            "className": "mpicbg.trakem2.transform.AffineModel2D",
            "dataString": "1.0 0.0 0.0 1.0 0.0 0.0",
            "type": "leaf"},
        "children": [{"stack": "CHILDSTACK1",
                      "transform": {
                          "className": "mpicbg.trakem2.transform.AffineModel2D",
                          "dataString": "1.0 0.0 0.0 1.0 0.0 0.0",
                          "type": "leaf"},
                      "children": [{"stack": "CHILDSTACK2",
                                    "transform": {
                                        "className": "mpicbg.trakem2.transform.AffineModel2D",
                                        "dataString": "1.0 0.0 0.0 1.0 0.0 0.0",
                                        "type": "leaf"},
                                    "children": []}]}]},
    "pool_size": 12,
    "interpolate_transforms": True,  # False is notimplemented
    "output_stack": "FUSEDOUTSTACK",
    "create_nonoverlapping_zs": True
}


class FuseStacksModule(RenderModule):
    default_schema = FuseStacksParameters
    default_output_schema = FuseStacksOutput

    def fusetoparent(self, parent, child, transform=None,
                     uninterpolated_zs=[]):
        transform = ([renderapi.transform.AffineModel()]
                     if transform is None else transform)
        parent = child if parent is None else parent

        # get overlapping zs
        parent_zs = set(self.render.run(
            renderapi.stack.get_z_values_for_stack, parent))
        child_zs = set(self.render.run(
            renderapi.stack.get_z_values_for_stack, child))
        z_intersection = sorted(parent_zs.intersection(child_zs))

        jsonfiles = []
        for z in uninterpolated_zs:
            section_tiles = []
            tspecs = renderapi.tilespec.get_tile_specs_from_z(
                child, z, render=self.render)
            for ts in tspecs:
                tsc = copy.deepcopy(ts)
                # tsc.tforms.append(transform)  # TODO for nonconcat
                tsc.tforms.extend(transform[::-1])
                section_tiles.append(tsc)
            jsonfiles.append(renderapi.utils.renderdump_temp(section_tiles))

        # can check order relation of child/parent stack
        positive = max(child_zs) > z_intersection[-1]
        self.logger.debug("positive concatenation? {}".format(positive))

        # generate jsonfiles representing interpolated overlapping tiles
        for i, z in enumerate((
                z_intersection if positive else z_intersection[::-1])):
            section_tiles = []
            lambda_ = float(i / float(len(z_intersection)))

            atiles = {ts.tileId: ts for ts
                      in renderapi.tilespec.get_tile_specs_from_z(
                          parent, z, render=self.render)}
            btiles = {ts.tileId: ts for ts
                      in renderapi.tilespec.get_tile_specs_from_z(
                          child, z, render=self.render)}
            # generate interpolated tiles for intersection of set of tiles
            for tileId in viewkeys(atiles) & viewkeys(btiles):
                a = atiles[tileId]
                interp_tile = copy.deepcopy(a)
                b = btiles[tileId]
                # b.tforms.append(transform) # TODO for nonconcat
                b.tforms.extend(transform[::-1])
                a.tforms.extend(transform[:-1][::-1])

                interp_tile.tforms = [
                    renderapi.transform.InterpolatedTransform(
                        a=renderapi.transform.TransformList(a.tforms),
                        b=renderapi.transform.TransformList(b.tforms),
                        lambda_=lambda_)]
                section_tiles.append(interp_tile)
            jsonfiles.append(renderapi.utils.renderdump_temp(section_tiles))
        return jsonfiles

    def fuse_graph(self, node, parentstack=None, inputtransform=None,
                   create_nonoverlapping_zs=False):
        inputtransform = ([]
                          if inputtransform is None else inputtransform)
        node_edge = (renderapi.transform.AffineModel()
                     if node.get('transform') is None
                     else renderapi.transform.load_transform_json(
                         node['transform']))
        # concatenate edge and input transform -- expected to work for Aff Hom
        node_tformlist = inputtransform + [node_edge]  # TODO trial
        # node_tform = node_edge.concatenate(inputtransform)
        # node_tform = inputtransform.concatenate(node_edge)

        # determine zs which can be rendered uninterpolated (but tformed)
        # TODO maybe there's a better way to handle this
        # -- or move within  fusetoparent
        parentzs = (set(renderapi.stack.get_z_values_for_stack(
            parentstack, render=self.render))
                    if parentstack is not None else {})
        nodezs = set(renderapi.stack.get_z_values_for_stack(
            node['stack'], render=self.render))
        childzs = (
            {zval for zlist in (
                renderapi.stack.get_z_values_for_stack(
                    c['stack'], render=self.render)
                for c in node['children']) for zval in zlist}
            if len(node['children']) else {})
        uninterpolated_zs = nodezs.difference(parentzs).difference(childzs)

        # generate and upload interpolated tiles
        jfiles = self.fusetoparent(
            parentstack, node['stack'],
            uninterpolated_zs=uninterpolated_zs,
            transform=node_tformlist)  # TODO trial
        renderapi.stack.create_stack(
            self.args['output_stack'], render=self.render)
        renderapi.client.import_jsonfiles_parallel(
            self.args['output_stack'], jfiles,
            pool_size=self.args['pool_size'],
            close_stack=False, render=self.render)

        # clean up temporary files
        for jfile in jfiles:
            os.remove(jfile)

        # recurse through depth of graph
        for child in node['children']:
            self.fuse_graph(
                child, parentstack=node['stack'], inputtransform=node_tformlist)  # TODO nonconcat

    def run(self):
        self.fuse_graph(
            self.args['stacks'],
            create_nonoverlapping_zs=self.args['create_nonoverlapping_zs'])
        d = {'stack': self.args['output_stack']}
        self.output(d)


if __name__ == "__main__":
    mod = FuseStacksModule(input_data=example_parameters)
    mod.run()
