import argschema
from argschema import InputDir
import marshmallow as mm
from marshmallow import post_load, ValidationError
from argschema.fields import (
        Bool, Float, Int,
        Str, InputFile, List, Dict)
from argschema.schemas import DefaultSchema

from asap.module.schemas import (
        RenderParameters,
        StackTransitionParameters)


class MakeAnchorStackSchema(StackTransitionParameters):
    transform_xml = InputFile(
        required=False,
        description=("xml transforms from trakem"
                     "images from which these are made"
                     "are assumed to be named <z>_*.png"))
    transform_json = InputFile(
        required=False,
        default=None,
        missing=None,
        description=("Human generated list of transforms."
                     "or, json scraped from xml"
                     "Keys are of form <z>_*.png where z matches "
                     "a tilespec in input_stack and values are "
                     "AffineModel transform jsons"
                     "will override xml input."))
    zValues = List(
            Int,
            required=False,
            missing=[1000],
            default=[1000],
            description="not used in this module, keeps parents happy")


class PairwiseRigidSchema(StackTransitionParameters):
    match_collection = Str(
        required=True,
        description="Point match collection name")
    gap_file = InputFile(
        required=False,
        default=None,
        missing=None,
        description="json file {k: v} where int(k) is a z value to skip"
                    "entries in here that are not already missing will"
                    "be omitted from the output stack"
                    "i.e. this is a place one can skip sections")
    translate_to_positive = Bool(
        required=False,
        default=True,
        missing=True,
        description="translate output stack to positive space")
    translation_buffer = List(
        Float,
        required=False,
        default=[0, 0],
        missing=[0, 0],
        description=("minimum (x, y) of output stack if "
                     "translate_to_positive=True"))
    anchor_stack = Str(
        require=False,
        default=None,
        missing=None,
        description=("fix transforms using tiles in this stack"))


class PairwiseRigidOutputSchema(DefaultSchema):
    minZ = Int(
        required=True,
        description="minimum z value in output stack")
    maxZ = Int(
        required=True,
        description="minimum z value in output stack")
    output_stack = Str(
        required=True,
        description="name of output stack")
    missing = List(
        Int,
        required=True,
        description="list of z values missing in z range of output stack")
    masked = List(
        Int,
        required=True,
        description="list of z values masked in z range of output stack")
    residuals = List(
        Dict,
        required=True,
        description="pairwise residuals in output stack")


class ApplyRoughAlignmentTransformParameters(RenderParameters):
    montage_stack = mm.fields.Str(
        required=True,
        description='stack to make a downsample version of')
    prealigned_stack = mm.fields.Str(
        required=False,
        default=None,
        missing=None,
        description=(
            "stack with dropped tiles corrected for stitching errors"))
    lowres_stack = mm.fields.Str(
        required=True,
        description='montage scape stack with rough aligned transform')
    output_stack = mm.fields.Str(
        required=True,
        description='output high resolution rough aligned stack')
    tilespec_directory = mm.fields.Str(
        required=True,
        description='path to save section images')
    map_z = mm.fields.Boolean(
        required=False,
        default=False,
        missing=False,
        description=(
            'map the montage Z indices to the rough alignment '
            'indices (default - False)'))
    remap_section_ids = mm.fields.Boolean(
        required=False,
        default=False,
        missing=False,
        description=(
            'map section ids as well with the new z '
            'mapping. Default = False'))
    consolidate_transforms = mm.fields.Boolean(
        required=False,
        default=True,
        missing=True,
        description=(
            'should the transforms be consolidated? (default - True)'))
    scale = mm.fields.Float(
        required=True,
        description='scale of montage scapes')
    apply_scale = mm.fields.Boolean(
        required=False,
        default=False,
        missing=False,
        description='do you want to apply scale')
    pool_size = mm.fields.Int(
        require=False,
        default=10,
        missing=10,
        description='pool size for parallel processing')
    new_z = List(
        Int,
        required=False,
        default=None,
        cli_as_single_argument=True,
        description="List of new z values to be mapped to")
    old_z = List(
        Int,
        required=True,
        cli_as_single_argument=True,
        description="List of z values to apply rough alignment to")
    mask_input_dir = InputDir(
        required=False,
        default=None,
        missing=None,
        description=("directory containing mask files. basenames of "
                     "masks that match tileIds in the rough stack "
                     "will be handled."))
    read_masks_from_lowres_stack = Bool(
        required=False,
        default=False,
        missing=False,
        description=("masks will be taken from lowres tilespecs."
                     " any mask_input_dir ignored."))
    update_lowres_with_masks = Bool(
        required=False,
        default=False,
        description="should the masks be added to the rough stack?")
    filter_montage_output_with_masks = Bool(
        required=False,
        default=False,
        description="should the tiles written be filtered by the masks?")
    mask_exts = List(
        Str,
        required=False,
        default=['png', 'tif'],
        description="what kind of mask files to recognize")
    close_stack = argschema.fields.Bool(
        required=False, default=True,
        missing=True, description=(
            "whether to set output stack to COMPLETE"))

    @post_load
    def validate_data(self, data):
        if data['prealigned_stack'] is None:
            data['prealigned_stack'] = data['montage_stack']
        if data['map_z']:
            if data['new_z'] is None:
                raise ValidationError("new_z is invalid. "
                                      "You need to specify new_z "
                                      "as a list of values")
            elif abs(len(data['new_z']) - len(data['old_z'])) != 0:
                raise ValidationError("new_z list count does "
                                      "not match with old_z list count")
        else:
            data['new_z'] = data['old_z']
            data['remap_section_ids'] = False


class LowresStackParameters(DefaultSchema):
    stack = Str(
        required=True,
        description="Input downsample images section stack")
    owner = Str(
        required=False,
        default=None,
        missing=None,
        description="Owner of the input lowres stack")
    project = Str(
        required=False,
        default=None,
        missing=None,
        description="Project of the input lowres stack")
    service_host = Str(
        required=False,
        default=None,
        missing=None,
        description="Service host for the input stack Render service")
    baseURL = Str(
        required=False,
        default=None,
        missing=None,
        description="Base URL of the Render service for the source stack")
    renderbinPath = Str(
        required=False,
        default=None,
        missing=None,
        description="Client scripts location")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="Want the output to be verbose?")


class OutputLowresStackParameters(DefaultSchema):
    stack = Str(
        required=True,
        description="Input downsample images section stack")
    owner = Str(
        required=False,
        default=None,
        missing=None,
        description="Owner of the input lowres stack")
    project = Str(
        required=False,
        default=None,
        missing=None,
        description="Project of the input lowres stack")
    service_host = Str(
        required=False,
        default=None,
        missing=None,
        description="Service host for the input stack Render service")
    baseURL = Str(
        required=False,
        default=None,
        missing=None,
        description="Base URL of the Render service for the source stack")
    renderbinPath = Str(
        required=False,
        default=None,
        missing=None,
        description="Client scripts location")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="Want the output to be verbose?")


class PointMatchCollectionParameters(DefaultSchema):
    owner = Str(
        required=False,
        default=None,
        missing=None,
        description="Point match collection owner (defaults to render owner")
    match_collection = Str(
        required=True,
        description="Point match collection name")
    server = Str(
        required=False,
        default=None,
        missing=None,
        description="baseURL of the Render service holding the "
                    "point match collection")
    verbose = Int(
        required=False,
        default=0,
        missing=0,
        description="Verbose output flag")


class ApplyRoughAlignmentOutputParameters(DefaultSchema):
    zs = argschema.fields.NumpyArray(
            description="list of z values that were applied to")
    output_stack = argschema.fields.Str(
            description="stack where applied transforms were set")


class DownsampleMaskHandlerSchema(RenderParameters):
    stack = argschema.fields.Str(
        required=True,
        description="stack that is read and modified with masks")
    close_stack = argschema.fields.Bool(
        required=True,
        default=True,
        description="set COMPLETE or not")
    mask_dir = argschema.fields.InputDir(
        required=True,
        default=None,
        description=("directory containing masks, named <z>_*.png where"
                     "<z> is a z value in input_stack and may be specified"
                     "in z_apply"))
    collection = argschema.fields.Str(
        required=True,
        default=None,
        description=("name of collection to be filtered by mask, or reset"
                     "can be None for no operation"))
    zMask = argschema.fields.List(
        argschema.fields.Int,
        required=False,
        default=None,
        missing=None,
        cli_as_single_argument=True,
        description=("z values for which the masks will be set"))
    zReset = argschema.fields.List(
        argschema.fields.Int,
        required=False,
        default=None,
        missing=None,
        cli_as_single_argument=True,
        description=("z values for which the masks will be reset"))
    mask_exts = List(
        Str,
        required=False,
        default=['png', 'tif'],
        description="what kind of mask files to recognize")
