#!/usr/bin/env python
"""
verify and validate tilesource directory
"""
import errno
import os
from multiprocessing.pool import ThreadPool

import argschema
import imageio

from rendermodules.materialize.schemas import (
    ValidateMaterializationParameters, ValidateMaterializationOutput)


example_input = {
    "minRow": 176,
    "maxRow": 196,
    "minCol": 176,
    "maxCol": 196,
    "minZ": 1849,
    "maxZ": 1855,
    "basedir": "/allen/programs/celltypes/production/wijem/materialization/17797_1R/17797_1R/em_rough_align_zs1849_ze2378_txy80k/1024x1024",
    "pool_size": 20
}


class ValidateMaterialization(argschema.ArgSchemaParser):
    default_schema = ValidateMaterializationParameters
    default_output_schema = ValidateMaterializationOutput

    @staticmethod
    def tilefile_from_ts5(basedir, z, row, col, ext, mmL=0):
        return os.path.join(
            basedir, str(mmL), str(z), str(row), "{}.{}".format(col, ext))

    @staticmethod
    def try_load_file(fn, allow_ENOENT=True, allow_EACCES=False):
        try:
            with open(fn, 'rb') as f:
                img = imageio.imread(f)
            del img
        except (IOError, ValueError, SyntaxError) as e:
            if isinstance(e, IOError):
                if allow_ENOENT and (e.errno == errno.ENOENT):
                    return True
                elif not allow_EACCES and (e.errno == errno.EACCES):
                    raise
            else:
                return
        return True

    @classmethod
    def try_load_tile(cls, tile_fn):
        return tile_fn if cls.try_load_file(tile_fn) is None else None

    def build_tilefiles(self, basedir, minZ, maxZ, minRow, maxRow,
                        minCol, maxCol, ext, mmL=0):
        for z in range(minZ, maxZ + 1):
            for r in range(minRow, maxRow + 1):
                for c in range(minCol, maxCol + 1):
                    yield self.tilefile_from_ts5(basedir, z, r, c, ext, mmL)

    def run(self):
        tile_files = self.build_tilefiles(
            self.args['basedir'], self.args['minZ'], self.args['maxZ'],
            self.args['minRow'], self.args['maxRow'],
            self.args['minCol'], self.args['maxCol'], self.args['ext'])
        pool = ThreadPool(self.args.get('pool_size'))
        bad_files = filter(None, pool.imap_unordered(
            self.try_load_tile, tile_files))
        self.output({
            "basedir": self.args["basedir"],
            "failures": [i for i in bad_files]
        })


if __name__ == "__main__":
    mod = ValidateMaterialization(input_data=example_input)
    mod.run()
