#!/usr/bin/env python
"""
verify and validate tilesource directory
"""
import errno
import os
from multiprocessing.pool import ThreadPool

import argschema
import imageio

from asap.materialize.schemas import (
    ValidateMaterializationParameters, ValidateMaterializationOutput)

try:
    xrange
except NameError:
    xrange = range


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

    @staticmethod
    def rows_from_ts5(basedir, z, mmL=0):
        for d in os.listdir(os.path.join(basedir, str(mmL), str(z))):
            if d.isdigit():
                yield int(d)

    @staticmethod
    def cols_from_ts5(basedir, z, row, ext, mmL=0):
        # TODO make ext work for filtering
        for fn in os.listdir(os.path.join(
                basedir, str(mmL), str(z), str(row))):
            if os.path.splitext(fn)[0].isdigit():
                yield int(os.path.splitext(fn)[0])

    @classmethod
    def build_tilefiles(cls, basedir, minZ, maxZ, minRow=None, maxRow=None,
                        minCol=None, maxCol=None, ext="png", mmL=0):
        for z in xrange(minZ, maxZ + 1):
            if minRow is None or maxRow is None:
                allrows = sorted(cls.rows_from_ts5(basedir, z, mmL))
                if minRow is None:
                    minRow = allrows[0]
                if maxRow is None:
                    maxRow = allrows[-1]
            # this checks for thing that don't necessarily exist.
            for r in xrange(minRow, maxRow + 1):
                if minCol is None or maxCol is None:
                    allcols = sorted(cls.cols_from_ts5(
                        basedir, z, r, ext, mmL))
                    if minCol is None:
                        minCol = allcols[0]
                    if maxCol is None:
                        maxCol = allcols[-1]
                for c in xrange(minCol, maxCol+1):
                    yield cls.tilefile_from_ts5(basedir, z, r, c, ext, mmL)

    def run(self):
        tile_files = self.build_tilefiles(
            self.args['basedir'], self.args['minZ'], self.args['maxZ'],
            self.args.get('minRow'), self.args.get('maxRow'),
            self.args.get('minCol'), self.args.get('maxCol'), self.args['ext'])
        pool = ThreadPool(self.args.get('pool_size'))
        bad_files = filter(None, pool.imap_unordered(
            self.try_load_tile, tile_files))
        self.output({
            "basedir": self.args["basedir"],
            "failures": [i for i in bad_files]
        })


if __name__ == "__main__":
    mod = ValidateMaterialization()
    mod.run()
