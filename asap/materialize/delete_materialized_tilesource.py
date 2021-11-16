#!/usr/bin/env python
"""
delete materializations in a tilesource directory
"""
import errno
import os
from multiprocessing.pool import ThreadPool

import argschema

from asap.materialize.schemas import (
    DeleteMaterializedSectionsParameters, DeleteMaterializedSectionsOutput)

example_input = {
  "minZ": 19750,
  "maxZ": 19750,
  "basedir": "/allen/programs/celltypes/production/wijem/workflow_data/production/chunk_30_zs19713_ze20389/17797_1R/FUSEDOUTSTACK/1024x1024",
  "pool_size": 20
}


class DeleteMaterializedSectionsModule(argschema.ArgSchemaParser):
    default_schema = DeleteMaterializedSectionsParameters
    default_output_schema = DeleteMaterializedSectionsOutput

    @staticmethod
    def get_ts5_tiles(basedir, zs, levels=None):
        levels = ([int(lvl) for lvl in os.listdir(basedir) if lvl.isdigit()]
                  if levels is None else levels)
        for lvl in sorted(levels):
            lvldir = os.path.join(basedir, str(lvl))
            for z in zs:
                zdir = os.path.join(lvldir, str(z))
                try:
                    for r in os.listdir(zdir):
                        rowdir = os.path.join(zdir, r)
                        # python2 compatible
                        for cfile_basename in os.listdir(rowdir):
                            yield os.path.join(rowdir, cfile_basename)
                except OSError as e:
                    if e.errno == errno.ENOENT:
                        pass
                    else:
                        raise

    @staticmethod
    def get_ts5_directories(basedir, zs, levels=None):
        levels = ([int(lvl) for lvl in os.listdir(basedir) if lvl.isdigit()]
                  if levels is None else levels)
        for lvl in sorted(levels):
            lvldir = os.path.join(basedir, str(lvl))
            for z in zs:
                zdir = os.path.join(lvldir, str(z))
                try:
                    for r in os.listdir(zdir):
                        rowdir = os.path.join(zdir, r)
                        yield rowdir
                except OSError as e:
                    if e.errno == errno.ENOENT:
                        pass
                    else:
                        raise
                yield zdir

    @classmethod
    def get_z_tiles(cls, basedir, zs, tilesource, *args, **kwargs):
        tilefn_generator_map = {5: cls.get_ts5_tiles}
        return tilefn_generator_map[tilesource](basedir, zs, *args, **kwargs)

    @classmethod
    def get_z_directories(cls, basedir, zs, tilesource, *args, **kwargs):
        dirname_generator_map = {5: cls.get_ts5_directories}
        return dirname_generator_map[tilesource](basedir, zs, *args, **kwargs)

    def run(self):
        pool = ThreadPool(self.args['pool_size'])
        zs = list(range(self.args['minZ'], self.args['maxZ'] + 1))
        pool.map(os.remove, self.get_z_tiles(
            self.args['basedir'],
            zs,
            self.args['tilesource']))
        for d in self.get_z_directories(
                self.args['basedir'], zs, self.args['tilesource']):
            try:
                os.removedirs(d)  # should only remove empty directories
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise


if __name__ == "__main__":
    mod = DeleteMaterializedSectionsModule()
    mod.run()
