#!/usr/bin/env python
"""
create tilespecs from TEMCA metadata file
"""

import json
import os
import pathlib
import numpy
import renderapi
import argschema
from argschema.fields import InputFile, Str, Int, Boolean, InputDir
from rendermodules.module.render_module import (RenderModule, RenderParameters)

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


class GenerateEMTileSpecsParameters(RenderParameters):
    metafile = InputFile(
        required=True,
        description="metadata file containing TEMCA acquisition data")
    stack = Str(required=True,
                description="stack to which tiles should be added")
    image_directory = InputDir(
        required=False,
        description=("directory used in determining absolute paths to images. "
                     "Defaults to parent directory containing metafile "
                     "if omitted."))
    pool_size = Int(
        required=False, default=1,
        description="processes to spawn for parallelization")
    close_stack = Boolean(
        required=False, default=False,
        description=("whether to set stack to 'COMPLETE' after "
                     "performing operation"))
    overwrite_zlayer = Boolean(
        required=False, default=False,
        description=("whether to remove the existing layer from the "
                     "target stack before uploading."))
    maximum_intensity = Int(
        required=False, default=255,
        description=("intensity value to interpret as white"))
    minimum_intensity = Int(
        required=False, default=0,
        description=("intensity value to interpret as black"))
    z_index = Int(
        required=True,
        description="z value to which tilespecs from ROI will be added")
    sectionId = Str(
        required=False,
        description=("sectionId to apply to tiles during ingest.  "
                     "If unspecified will default to a string "
                     "representation of the float value of z_index."))


class GenerateEMTileSpecsOutput(argschema.schemas.mm.Schema):
    stack = Str(required=True,
                description="stack to which generated tiles were added")


class GenerateEMTileSpecsModule(RenderModule):
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
            z=str(float(self.args['z_index'])))

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
            imageRow=imgdata['img_meta']['raster_pos'][0],
            imageCol=imgdata['img_meta']['raster_pos'][1],
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
            z=self.args['z_index'], sectionId=self.args.get('sectionId'),
            scopeId=roidata['temca_id'],
            cameraId=roidata['camera_info']['camera_id'],
            pixelsize=pixelsize) for img in imgdata]

        # create stack if it does not exists, or set to loading if it does
        renderapi.stack.create_stack(self.args['stack'], render=self.render)
        if self.args['overwrite_zlayer']:
            try:
                renderapi.stack.delete_section(
                    self.args['stack'], self.args['z_index'],
                    render=self.render)
            except renderapi.errors.RenderError as e:
                self.logger.error(e)
        renderapi.client.import_tilespecs_parallel(
            self.args['stack'], tspecs,
            poolsize=self.args['pool_size'],
            close_stack=self.args['close_stack'], render=self.render)

        try:
            self.output({'stack': self.args['stack']})
        except AttributeError as e:
            self.logger.error(e)


if __name__ == "__main__":
    mod = GenerateEMTileSpecsModule(input_data=example_input)
    mod.run()
