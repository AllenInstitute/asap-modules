#!/usr/bin/env python

from argschema import ArgSchema
from argschema.schemas import DefaultSchema
from argschema.fields import String, Int, Boolean, Nested, Float, Str, OutputDir
from marshmallow import ValidationError
from ..module.render_module import RenderParameters


class regularization(ArgSchema):
    default_lambda = Float(
        required=False,
        default=0.005,
        missing=0.005,
        description="regularization factor")
    translation_factor = Float(
        required=False,
        default=0.005,
        missing=0.005,
        description="regularization factor")
    lens_lambda = Float(
        required=False,
        default=0.005,
        missing=0.005,
        description="regularization for lens parameters")


class RawLensStackSchema(RenderParameters):
    #render = Nested(render)
    #stack = String(
    #    required=True,
    #    description="nameof stack for writing raw tilespecs")
    metafile = String(
        required=True,
        description="fullpath of metadata file")
    overwrite_zlayer = Boolean(
        required=False,
        default=True,
        missing=True,
        description="")
    pool_size = Int(
        required=False,
        default=10,
        description="")
    close_stack = Boolean(
        required=False,
        default=True,
        description="")
    z_index = Int(
        required=True,
        description="z value for the lens correction data in stack")


class LensPointMatchSchema(RawLensStackSchema):
    input_stack = String(
        required=True,
        description="Name of raw input lens data stack")
    match_collection = String(
        required=True,
        description="name of point match collection")
    tilepair_output = String(
        required=False,
        default="",
        description="path to tilepair json file")
    pairJson = String(
        required=False,
        default="",
        description="path to tilepair json file")
    nfeature_limit = Int(
        required=False,
        default=20000,
        missing=20000,
        description="randomly choose this many features per tile")
    matchMax = Int(
        required=False,
        default=1000,
        missing=1000,
        description="maximum pointmatches per tile pair")
    ncpus = Int(
        required=False,
        default=-1,
        description="max number of cpus to use")
    downsample_scale = Float(
        required=False,
        default=0.3,
        missing=0.3,
        description="passed to cv2.resize fx,fy")


class LensCorrectionSchema(LensPointMatchSchema):
    #aligned_stack = String(
    #    required=True,
    #    description="name of stack after correction and alignment")
    nvertex = Int(
        required=False,
        default=1000,
        missinf=1000,
        description="maximum number of vertices to attempt")
    sectionId = String(
        required=False,
        default="",
        missing="",
        description="sectionId for creating correction")
    render_output = String(
        defult=None,
        description="path, null, or stdout")
    output_stack = String(
        required=True,
        description="Name of the lens corrected output stack")
    output_dir = OutputDir(
        required=False,
        default=None,
        description="write lens correction tform jsons here")
    outfile = Str(
        required=False,
        default=None,
        missing=None,
        description=("File to which json output of lens correction "
                     "(leaf TransformSpec) is written"))
    out_html_dir = OutputDir(
        required=False,
        default=None,
        description="where to write some qc files")
    regularization = Nested(regularization)


class LensCorrectionOutputSchema(DefaultSchema):
    output_json = String(
        required=True,
        description="path to file")
    qc_json = String(
        required=True,
        description="path to qc json file")

