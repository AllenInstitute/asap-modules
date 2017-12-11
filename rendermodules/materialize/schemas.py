
from marshmallow import ValidationError, validates_schema
import argschema
from argschema.fields import InputDir, InputFile, Str, Int, Float, Boolean, OutputDir
from ..module.schemas import RenderParameters


class RenderSectionAtScaleParameters(RenderParameters):
    input_stack = Str(
        required=True,
        description='Input stack to make the downsample version of')
    #output_stack = Str(
    #    required=True,
    #    description='Name of the output downsample stack')
    image_directory = OutputDir(
        required=True,
        description='Directory to save the downsampled sections')
    imgformat = Str(
        required=False,
        default="png",
        missing="png",
        description='Image format (default -  png)')
    doFilter = Boolean(
        required=False,
        default=True,
        missing=True,
        description='Apply filtering before rendering')
    fillWithNoise = Boolean(
        required=False,
        default=False,
        missing=False,
        description='Fill image with noise (default - False)')
    scale = Float(
        required=True,
        description='scale of the downsampled sections')
    minZ = Int(
        required=False,
        default=-1,
        missing=-1,
        description='min Z to create the downsample section from')
    maxZ = Int(
        required=False,
        default=-1,
        missing=-1,
        description='max Z to create the downsample section from')
    pool_size = Int(
        required=False,
        default=20,
        missing=20,
        description='number of parallel threads to use')

class RenderSectionAtScaleOutput(argschema.schemas.DefaultSchema):
    image_directory = InputDir(
        required=True,
        description='Directory in which the downsampled section images are saved')
