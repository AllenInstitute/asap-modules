#!/usr/bin/env python
'''
define a transformation to register the overlapping portion
    of two aligned subvolumes
'''

import numpy
import renderapi
from six import viewkeys, iteritems

from asap.module.render_module import RenderModule
from asap.fusion.schemas import (
    RegisterSubvolumeParameters,
    RegisterSubvolumeOutputParameters)

example_parameters = {
    "render": {
        "host": "em-131fs",
        "port": 8080,
        "owner": "testuser",
        "project": "test",
        "client_scripts": ""
    },
    "stack_a": "PARENTSTACK",
    "stack_b": "CHILDSTACK",
    "transform_type": "RIGID",
    "pool_size": 12
}


class RegisterSubvolumeModule(RenderModule):
    default_schema = RegisterSubvolumeParameters
    default_output_schema = RegisterSubvolumeOutputParameters

    transform_classes = {'TRANSLATION': renderapi.transform.TranslationModel,
                         'RIGID': renderapi.transform.RigidModel,
                         'SIMILARITY': renderapi.transform.SimilarityModel,
                         'AFFINE': renderapi.transform.AffineModel}

    def run(self):
        a = self.args['stack_a']
        b = self.args['stack_b']
        r = self.render

        # initialize empty set
        acoord = numpy.empty([0, 2])
        bcoord = numpy.empty([0, 2])
        # only interested in registering zs in both stacks
        for z in set(r.run(
            renderapi.stack.get_z_values_for_stack, a)).intersection(
                set(r.run(renderapi.stack.get_z_values_for_stack, b))):
            atileIdtoTiles = {ts.tileId: ts for ts in r.run(
                renderapi.tilespec.get_tile_specs_from_z, a, z)}
            btileIdtoTiles = {ts.tileId: ts for ts in r.run(
                renderapi.tilespec.get_tile_specs_from_z, b, z)}
            # only interested in tiles in both stacks
            tilestomatch = (viewkeys(atileIdtoTiles) &
                            viewkeys(btileIdtoTiles))
            self.logger.debug(
                'matching {} tiles from z {}'.format(len(tilestomatch), z))

            # generate centerpoints to use render for dest pts
            #     TODO is it worthwhile to generate a grid/mesh as in PEA?
            centerpoint_l2win = [
                {'tileId': tileId, 'visible': False,
                 'local': [atile.width // 2, atile.height // 2]}
                for tileId, atile in iteritems(atileIdtoTiles)
                if tileId in tilestomatch]

            # get world coordinates for a and b
            # TODO currently server-side
            wc_a = renderapi.coordinate.local_to_world_coordinates_batch(
                a, centerpoint_l2win, z,
                number_of_threads=self.args['pool_size'], render=r)
            wc_b = renderapi.coordinate.local_to_world_coordinates_batch(
                b, centerpoint_l2win, z,
                number_of_threads=self.args['pool_size'], render=r)

            # format world coordinate json to matching numpy arrays
            acoord = numpy.vstack([
                acoord, numpy.array([d['world'][:2] for d in wc_a])])
            bcoord = numpy.vstack([
                bcoord, numpy.array([d['world'][:2] for d in wc_b])])

        # initialize homography tform and then estimate
        tform = self.transform_classes[
            self.args['transform_type']]()
        tform.estimate(bcoord, acoord, return_params=False)
        self.logger.info('transform found: {}'.format(tform))

        out_json = {'stack_a': self.args['stack_a'],
                    'stack_b': self.args['stack_b'],
                    'transform': tform.to_dict()}
        self.output(out_json)


if __name__ == "__main__":
    mod = RegisterSubvolumeModule()
    mod.run()
