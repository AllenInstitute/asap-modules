#!/usr/bin/env python
'''
fuse overlapping render stacks registered by an Affine Homography transform
    similar to Parallel Elastic Alignment
'''
import copy

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
    "create_nonoverlapping_zs": True,
    "close_stack": False,
    "max_tilespecs_per_import_process": 5000
}


class FuseStacksModule(RenderModule):
    default_schema = FuseStacksParameters
    default_output_schema = FuseStacksOutput

    def fusetoparent(self, parent, child, transform=None,
                     interpolated_zs=None, uninterpolated_zs=[]):
        transform = ([renderapi.transform.AffineModel()]
                     if transform is None else transform)
        parent = child if parent is None else parent

        # get overlapping zs
        parent_zs = set(self.render.run(
            renderapi.stack.get_z_values_for_stack, parent))
        child_zs = set(self.render.run(
            renderapi.stack.get_z_values_for_stack, child))
        z_intersection = sorted((
            parent_zs.intersection(child_zs) if interpolated_zs is None
            else interpolated_zs))

        resolved_tspecs = []
        all_resolved_tform = []
        for z in uninterpolated_zs:
            section_tiles = []
            resolved = renderapi.resolvedtiles.get_resolved_tiles_from_z(
                child, z, render=self.render)
            all_resolved_tform += resolved.transforms
            for ts in resolved.tilespecs:
                tsc = copy.deepcopy(ts)
                # tsc.tforms.append(transform)  # TODO for nonconcat
                tsc.tforms.extend(transform[::-1])
                resolved_tspecs.append(tsc)

        if set(uninterpolated_zs) == set(parent_zs).union(set(child_zs)):
            # standalone uninterplated case
            return renderapi.resolvedtiles.ResolvedTiles(
                tilespecs=resolved_tspecs,
                transformList=all_resolved_tform)

        if interpolated_zs:
            # can check order relation of child/parent stack
            positive = max(child_zs) > z_intersection[-1]
            self.logger.debug("positive concatenation? {}".format(positive))

            # generate jsonfiles representing interpolated overlapping tiles
            for i, z in enumerate((
                    z_intersection if positive else z_intersection[::-1])):
                section_tiles = []
                lambda_ = float(i / float(len(z_intersection)))

                p_resolved = renderapi.resolvedtiles.get_resolved_tiles_from_z(
                    parent, z, render=self.render)
                c_resolved = renderapi.resolvedtiles.get_resolved_tiles_from_z(
                    child, z, render=self.render)

                all_resolved_tform += (p_resolved.transforms +
                                       c_resolved.transforms)

                atiles = {ts.tileId: ts for ts
                          in p_resolved.tilespecs}
                btiles = {ts.tileId: ts for ts
                          in c_resolved.tilespecs}
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
                    resolved_tspecs.append(interp_tile)
        resolved_tforms = list(
            {tform.transformId: tform
             for tform in all_resolved_tform}.values())
        return renderapi.resolvedtiles.ResolvedTiles(
            tilespecs=resolved_tspecs, transformList=resolved_tforms)

    def fuse_graph(self, node, parentstack=None, inputtransform=None,
                   fuse_parent=False, create_nonoverlapping_zs=False,
                   max_tilespecs_per_group=5000):
        inputtransform = ([]
                          if inputtransform is None else inputtransform)
        node_edge = (renderapi.transform.AffineModel()
                     if node.get('transform') is None
                     else renderapi.transform.load_transform_json(
                         node['transform']))
        # concatenate edge and input transform -- expected to work for Aff Hom
        node_tformlist = inputtransform + [node_edge]

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
        interpolated_zs = nodezs.intersection(parentzs)
        uninterpolated_zs = nodezs.difference(parentzs).difference(childzs)

        # only get interpolation/import if "fuse_stack" option is true
        if node.get("fuse_stack"):
            # generate and upload interpolated tiles
            resolvedtiles = self.fusetoparent(
                parentstack, node['stack'],
                interpolated_zs=(interpolated_zs if fuse_parent else set([])),
                uninterpolated_zs=uninterpolated_zs,
                transform=node_tformlist)

            if self.args['output_stack'] not in self.render.run(
                    renderapi.render.get_stacks_by_owner_project):
                renderapi.stack.create_stack(
                    self.args['output_stack'], render=self.render)
            self.render.run(renderapi.stack.set_stack_state,
                            self.args['output_stack'], 'LOADING')

            renderapi.client.import_tilespecs_parallel(
                self.args['output_stack'], resolvedtiles.tilespecs,
                resolvedtiles.transforms, pool_size=self.args['pool_size'],
                close_stack=False,
                max_tilespecs_per_group=max_tilespecs_per_group,
                render=self.render)

        # recurse through depth of graph
        for child in node['children']:
            self.fuse_graph(
                child, parentstack=node['stack'],
                fuse_parent=node['fuse_stack'],
                inputtransform=node_tformlist)

    def run(self):
        self.fuse_graph(
            self.args['stacks'],
            create_nonoverlapping_zs=self.args['create_nonoverlapping_zs'],
            max_tilespecs_per_group=self.args[
                'max_tilespecs_per_import_process'])
        if self.args['close_stack']:
            renderapi.stack.set_stack_state(
                self.args['output_stack'], "COMPLETE", render=self.render)
        d = {'stack': self.args['output_stack']}
        self.output(d)


if __name__ == "__main__":
    mod = FuseStacksModule(input_data=example_parameters)
    mod.run()
