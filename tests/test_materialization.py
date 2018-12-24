#!/usr/bin/env python
"""
test non-render (but related) materialization clients:
  tilesource 5 verification
  tilesource 5 deletion
"""
import errno
import collections
import json
import os
import random
import subprocess

import imageio
import numpy
from PIL import Image
import pytest

from rendermodules.materialize.validate_materialized_tilesource import (
    ValidateMaterialization)
from rendermodules.materialize.delete_materialized_tilesource import (
    DeleteMaterializedSectionsModule)

from tests_test_data import (TEST_MATERIALIZATION_JSON, pool_size)

MaterializedVolumeParams = collections.namedtuple(
    "MaterializedVolumeParams",
    ["project", "stack", "width", "height",
     "minRow", "maxRow", "minCol", "maxCol",
     "minZ", "maxZ", "ext"])


def generate_randomimg(fn, width, height):
    try:
        os.makedirs(os.path.dirname(fn))
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    tile_dims = width, height
    arr = numpy.random.randint(0, 256, size=tile_dims, dtype='uint8')
    img = Image.fromarray(arr)
    img.save(fn)
    return fn


@pytest.fixture(scope='function')
def basedir_mvparams_mvfiles(tmpdir):
    # NOTE basedir here is materialization input basedir
    basedir = str(tmpdir)

    mvparams = MaterializedVolumeParams(
        **TEST_MATERIALIZATION_JSON)
    mvfiles = [
        generate_randomimg(
            fn, mvparams.width, mvparams.height)
        for fn in ValidateMaterialization.build_tilefiles(
            os.path.join(
                basedir, mvparams.project, mvparams.stack, "{}x{}".format(
                    mvparams.width, mvparams.height)),
            mvparams.minZ, mvparams.maxZ,
            mvparams.minRow, mvparams.maxRow,
            mvparams.minCol, mvparams.maxCol, mvparams.ext)]
    yield basedir, mvparams, mvfiles
    for mvfn in mvfiles:
        try:
            os.remove(mvfn)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
    mvdirs = {os.path.dirname(mvfn) for mvfn in mvfiles}
    for mvd in mvdirs:
        try:
            os.removedirs(mvd)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise


def truncatefile(fn, l):
    """subprocess-based truncate for python2 on linux"""
    subprocess.call(["truncate", "-s", str(int(l)), fn])


@pytest.mark.parametrize("excluded_keys", [
    [], ["minRow", "maxRow",
         "minCol", "maxCol"]])
def test_validate_materialization(
        basedir_mvparams_mvfiles, tmpdir, excluded_keys):
    basedir, mvparams, mvfiles = basedir_mvparams_mvfiles
    materialized_basedir = os.path.join(
        basedir, mvparams.project, mvparams.stack,
        "{}x{}".format(mvparams.width, mvparams.height))
    # TODO different corruption tests for different exts
    truncfn, badfn = random.sample(mvfiles, 2)
    # truncate file causing truncated file ValueError on read
    truncbytes = os.path.getsize(truncfn)
    truncatefile(truncfn, truncbytes//2)
    with pytest.raises(ValueError):
        _ = imageio.imread(truncfn)
    # truncate file so that it is unreadable
    truncatefile(badfn, 0)
    with pytest.raises(ValueError):
        _ = imageio.imread(badfn)
    # TODO there are some png cases which lead to SyntaxErrors?
    # run validation
    output_json = os.path.join(str(tmpdir), 'valdation_output.json')
    d = {
        "minRow": mvparams.minRow,
        "maxRow": mvparams.maxRow,
        "minCol": mvparams.minCol,
        "maxCol": mvparams.maxCol,
        "minZ": mvparams.minZ,
        "maxZ": mvparams.maxZ,
        "basedir": materialized_basedir,
        "pool_size": pool_size
    }
    # exclude keys
    d = {k: v for k, v in d.items() if k not in excluded_keys}
    mod = ValidateMaterialization(
        input_data=d, args=['--output_json', output_json])
    mod.run()
    with open(output_json, 'r') as f:
        output_d = json.load(f)
    assert not set(output_d['failures']) ^ {truncfn, badfn}


def test_delete_materialization(basedir_mvparams_mvfiles):
    basedir, mvparams, mvfiles = basedir_mvparams_mvfiles
    materialized_basedir = os.path.join(
        basedir, mvparams.project, mvparams.stack,
        "{}x{}".format(mvparams.width, mvparams.height))
    # run deletion
    d = {
        "minZ": mvparams.minZ,
        "maxZ": mvparams.maxZ,
        "basedir": materialized_basedir,
        "pool_size": pool_size
    }
    mod = DeleteMaterializedSectionsModule(input_data=d, args=[])
    mod.run()
    # verify tiles deleted (removedirs should remove basedir)
    try:
        basedir_contents = {i for i in os.listdir(materialized_basedir)}
        assert not basedir_contents
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
