from argschema.schemas import DefaultSchema
from argschema.fields import (
        Str, Int, Bool,
        Nested, Float, OutputDir,
        InputFile, List, OutputFile)
import marshmallow

import asap.utilities.schema_utils
from asap.pointmatch.schemas import PointMatchOpenCVParameters


class regularization(DefaultSchema):
    default_lambda = Float(
        required=False,
        default=0.005,
        missing=0.005,
        description="regularization factor")
    translation_factor = Float(
        required=False,
        default=0.005,
        missing=0.005,
        description="transaltion factor")
    lens_lambda = Float(
        required=False,
        default=0.005,
        missing=0.005,
        description="regularization for lens parameters")


class good_solve_criteria(DefaultSchema):
    error_mean = Float(
        required=False,
        default=0.2,
        missing=0.2,
        description="maximum error mean [pixels]")
    error_std = Float(
        required=False,
        default=2.0,
        missing=2.0,
        description="maximum error std [pixels]")
    scale_dev = Float(
        required=False,
        default=0.1,
        missing=0.1,
        description="maximum allowed scale deviation from 1.0")


class MeshLensCorrectionSchema(PointMatchOpenCVParameters):
    input_stack = Str(
        required=True,
        description="Name of raw input lens data stack")
    output_stack = Str(
        required=True,
        description="Name of lens corrected output stack")
    overwrite_zlayer = Bool(
        required=False,
        default=True,
        missing=True,
        description="Overwrite z layer (default = True)")
    rerun_pointmatch = Bool(
        required=False,
        default=True,
        missing=True,
        description="delete pointmatch values and rerun")
    close_stack = Bool(
        required=False,
        default=True,
        missing=True,
        description="Close input stack")
    do_montage_QC = Bool(
        required=False,
        default=True,
        missing=True,
        description="perform montage QC on stack result")
    match_collection = Str(
        required=True,
        description="name of point match collection")
    metafile = Str(
        required=False,
        description="fullpath of metadata file")
    metafile_uri = Str(
        required=True,
        description="uri_handler uri of metafile object")
    z_index = Int(
        required=True,
        description="z value for the lens correction data in stack")
    ncpus = Int(
        required=False,
        default=-1,
        description="max number of cpus to use")
    nvertex = Int(
        required=False,
        default=1000,
        missing=1000,
        description="maximum number of vertices to attempt")
    output_dir = OutputDir(
        required=False,
        default=None,
        missing=None,
        description="output dir to save tile pair file and qc json")
    outfile = Str(
        required=True,
        description=("File to which json output of lens correction "
                     "(leaf TransformSpec) is written"))
    regularization = Nested(regularization, missing={})
    good_solve = Nested(good_solve_criteria, missing={})
    sectionId = Str(
        required=True,
        default="xxx",
        description="section Id")
    mask_coords = List(
        List(Int),
        required=False,
        default=None,
        missing=None,
        cli_as_single_argument=True,
        description="Nx2 list of in-order bound coordinates")
    mask_dir = OutputDir(
        required=False,
        default=None,
        missing=None,
        description="directory for saving masks")
    mask_file = InputFile(
        required=False,
        default=None,
        missing=None,
        description="explicit mask setting from file")

    @marshmallow.pre_load
    def metafile_to_uri(self, data):
        asap.utilities.schema_utils.posix_to_uri(
            data, "metafile", "metafile_uri")


class DoMeshLensCorrectionOutputSchema(DefaultSchema):
    output_json = Str(
        required=True,
        description="path to lens correction file")
    maskUrl = OutputFile(
        required=True,
        description="path to mask generated")
