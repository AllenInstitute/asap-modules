#!/usr/bin/env python
"""
create tilespecs from TEMCA metadata file
"""

import json
import os
import pathlib
import numpy
import renderapi
from rendermodules.module.render_module import (
    StackOutputModule, RenderModuleException)
from rendermodules.dataimport.schemas import (GenerateEMTileSpecsOutput,
                                              GenerateEMTileSpecsParameters)

example_input = {
    "render": {
        "host": "em-131fs",
        "port": 8080,
        "owner": "russelt",
        "project": "RENDERAPI_TEST",
        "client_scripts": (
            "/allen/programs/celltypes/workgroups/"
            "em-connectomics/russelt/render_mc.old/render-ws-java-client/"
            "src/main/scripts")},
    "metafile": "/allen/programs/celltypes/workgroups/em-connectomics/data/workflow_test_sqmm/001050/0/_metadata_20170829130146_295434_5LC_0064_01_redo_001050_0_.json",
    "stack": "TEST_IMPORT_FROMMD",
    "overwrite_zlayer": True,
    "pool_size": 10,
    "close_stack": True,
    "z_index": 1
}


class GenerateEMTileSpecsModule(StackOutputModule):
    default_schema = GenerateEMTileSpecsParameters
    default_output_schema = GenerateEMTileSpecsOutput

    @staticmethod
    def image_coords_from_stage(stage_coords, resX, resY, rotation):
        cr = numpy.cos(rotation)
        sr = numpy.sin(rotation)
        x = stage_coords[0] / resX
        y = stage_coords[1] / resY
        return (int(x * cr + y * sr),
                int(-x * sr + y * cr))

    def tileId_from_basename(self, fname):
        return '{bname}.{z}'.format(
            bname=os.path.splitext(os.path.basename(fname))[0],
            z=str(float(self.zValues[0])))

    @staticmethod
    def sectionId_from_z(z):
        return str(float(z))

    def ts_from_imgdata(self, imgdata, imgdir, x, y,
                        minint=0, maxint=255, maskUrl=None,
                        width=3840, height=3840, z=None, sectionId=None,
                        scopeId=None, cameraId=None, pixelsize=None):
        tileId = self.tileId_from_basename(imgdata['img_path'])
        sectionId = (self.sectionId_from_z(z) if sectionId is None
                     else sectionId)
        raw_tforms = [renderapi.transform.AffineModel(B0=x, B1=y)]
        imageUrl = pathlib.Path(
            os.path.abspath(os.path.join(
                imgdir, imgdata['img_path']))).as_uri()

        return renderapi.tilespec.TileSpec(
            tileId=tileId, z=z,
            width=width, height=height,
            minint=minint, maxint=maxint,
            tforms=raw_tforms,
            mipMapLevels=[
                renderapi.tilespec.MipMapLevel(
                    0, imageUrl=imageUrl, maskUrl=maskUrl)],
            sectionId=sectionId, scopeId=scopeId, cameraId=cameraId,
            imageCol=imgdata['img_meta']['raster_pos'][0],
            imageRow=imgdata['img_meta']['raster_pos'][1],
            stageX=imgdata['img_meta']['stage_pos'][0],
            stageY=imgdata['img_meta']['stage_pos'][1],
            rotation=imgdata['img_meta']['angle'], pixelsize=pixelsize)

    def run(self):
        with open(self.args['metafile'], 'r') as f:
            meta = json.load(f)
        roidata = meta[0]['metadata']
        imgdata = meta[1]['data']
        img_coords = {img['img_path']: self.image_coords_from_stage(
            img['img_meta']['stage_pos'],
            img['img_meta']['pixel_size_x_move'],
            img['img_meta']['pixel_size_y_move'],
            numpy.radians(img['img_meta']['angle'])) for img in imgdata}

        if not imgdata:
            raise RenderModuleException(
                "No relevant image metadata found for metafile {}".format(
                    self.args['metafile']))

        minX, minY = numpy.min(numpy.array(img_coords.values()), axis=0)
        # assume isotropic pixels
        pixelsize = roidata['calibration']['highmag']['x_nm_per_pix']

        imgdir = self.args.get(
            'image_directory', os.path.dirname(self.args['metafile']))

        tspecs = [self.ts_from_imgdata(
            img, imgdir,
            img_coords[img['img_path']][0] - minX,
            img_coords[img['img_path']][1] - minY,
            minint=self.args['minimum_intensity'],
            maxint=self.args['maximum_intensity'],
            width=roidata['camera_info']['width'],
            height=roidata['camera_info']['height'],
            z=self.zValues[0], sectionId=self.args.get('sectionId'),
            scopeId=roidata['temca_id'],
            cameraId=roidata['camera_info']['camera_id'],
            pixelsize=pixelsize) for img in imgdata]

        self.output_tilespecs_to_stack(tspecs)

        try:
            self.output({'stack': self.output_stack})
        except AttributeError as e:
            self.logger.error(e)


if __name__ == "__main__":
    mod = GenerateEMTileSpecsModule(input_data=example_input)
    mod.run()
