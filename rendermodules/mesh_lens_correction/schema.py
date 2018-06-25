#!/usr/bin/env python

from argschema import ArgSchema
from argschema.fields import String, Int, Boolean, Nested, Float
from marshmallow import ValidationError


class render(ArgSchema):
    owner = String(
        deafult="",
        required=False,
        description="owner")
    project = String(
        deafult="",
        required=False,
        description="project")
    host = String(
        default=None,
        required=False,
        description="render host")
    port = Int(
        default=8080,
        required=False,
        description="render port")
    client_scripts = String(
        deafult="/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
        required=False,
        description="render bin path")

    def validate_data(self, data):
        if data["host"] is None:
            raise ValidationError("Need render host")


class regularization(ArgSchema):
    default_lambda = Float(
        default=0.005,
        description="regularization factor")
    translation_factor = Float(
        default=0.005,
        description="regularization factor")
    lens_lambda = Float(
        default=0.005,
        description="regularization for lens parameters")


class RawLensStackSchema(ArgSchema):
    render = Nested(render)
    stack = String(
        deafult="",
        description="nameof stack for writing raw tilespecs")
    metafile = String(
        deafult="",
        description="fullpath of metadata file")
    overwrite_zlayer = Boolean(
        default=True,
        description="")
    pool_size = Int(
        default=10,
        description="")
    close_stack = Boolean(
        default=True,
        description="")
    z = Int(
        default=1,
        description="")


class LensPointMatchSchema(RawLensStackSchema):
    match_collection = String(
        deafult="",
        description="name of point match collection")
    tilepair_output = String(
        deafult="",
        description="path to tilepair json file")
    pairJson = String(
        deafult="",
        description="path to tilepair json file")
    nfeature_limit = Int(
        default=10000,
        required=False,
        description="randomly choose this many features per tile")
    matchMax = Int(
        default=1000,
        required=False,
        description="maximum pointmatches per tile pair")
    ncpus = Int(
        default=-1,
        required=False,
        description="max number of cpus to use")
    downsample_scale = Float(
        default=0.3,
        required=False,
        description="passed to cv2.resize fx,fy")


class LensCorrectionSchema(LensPointMatchSchema):
    aligned_stack = String(
        deafult="",
        description="name \
        of stack after correction and alignment")
    nvertex = Int(
        default=1000,
        required=True,
        description="maximum number of vertices to attempt")
    sectionId = String(
        deafult="",
        description="sectionId for creating correction")
    render_output = String(
        deafult="null",
        description="path, null, or stdout")
    output_dir = String(
        deafult="",
        description="write lens correction tform jsons here")
    out_html_dir = String(
        deafult="",
        description="where to write some qc files")
    regularization = Nested(regularization)
