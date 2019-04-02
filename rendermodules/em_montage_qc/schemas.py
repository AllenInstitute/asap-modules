import argschema
import marshmallow as mm 
from marshmallow import post_load
from ..module.schemas import (RenderParameters, ZValueParameters,
                              ProcessPoolParameters)
from argschema.fields import Bool, Int, Str, InputDir, OutputFile


class DetectMontageDefectsParameters(
        RenderParameters, ZValueParameters, ProcessPoolParameters):
    prestitched_stack = Str(
        required=True,
        description='Pre stitched stack (raw stack)')
    poststitched_stack = Str(
        required=True,
        description='Stitched montage stack')
    match_collection = Str(
        reuqired=True,
        description='Name of the montage point match collection')
    match_collection_owner = Str(
        required=False,
        default=None,
        missing=None,
        description='Name of the match collection owner')
    residual_threshold = Int(
        required=False,
        default=4,
        missing=4,
        description='threshold value to filter residuals for detecting seams (default = 4)')
    neighbors_distance = Int(
        required=False,
        default=80,
        missing=80,
        description='distance in pixels to look for neighboring points in seam detection (default = 60)')
    min_cluster_size = Int(
        required=False,
        default=12,
        missing=12,
        description='minimum number of point matches required in each cluster for taking it into account for seam detection (default = 7)')
    plot_sections = Bool(
        required=False,
        default=True,
        missing=True,
        description="Do you want to plot the sections with defects (holes or gaps)?. Will plot Bokeh plots in a html file")
    out_html_dir = InputDir(
        required=False,
        default=None,
        missing=None,
        description="Folder to save the Bokeh plot defaults to /tmp directory")

    @post_load
    def add_match_collection_owner(self, data):
        if data['match_collection_owner'] is None:
            data['match_collection_owner'] = data['render']['owner']


class DetectMontageDefectsParametersOutput(argschema.schemas.DefaultSchema):
    output_html = argschema.fields.List(
        argschema.fields.Str,
        required=False,
        default=None,
        description='Output html file with Bokeh plots showing holes and stitching gaps')
    qc_passed_sections = argschema.fields.List(
        argschema.fields.Int,
        required=True,
        description='List of sections that passed QC')
    hole_sections = argschema.fields.List(
        argschema.fields.Int,
        required=True,
        description='List of z values which failed QC and has holes')
    gap_sections = argschema.fields.List(
        argschema.fields.Int,
        required=True,
        description='List of z values which have stitching gaps')
    seam_sections = argschema.fields.List(
        argschema.fields.Int,
        required=True,
        description='List of z values which have seams detected')
    seam_centroids = argschema.fields.NumpyArray(
        dtype='object',
        required=True,
        description='An array of (x,y) positions of seams for each section with seams')



class RoughQCSchema(RenderParameters):
    input_downsampled_stack = Str(
        required=True,
        description="Pre rough aligned downsampled stack")
    output_downsampled_stack = Str(
        required=True,
        description="Rough aligned stack name")
    minZ = Int(
        required=True,
        description="min z")
    maxZ = Int(
        required=True,
        description="max z")
    pool_size = Int(
        required=False,
        default=10,
        missing=10,
        description="Pool size")
    output_dir = Str(
        required=False,
        default=None,
        missing=None,
        description="temp filename to save fig")
    out_file_format = Str(
        validator=mm.validate.OneOf(['html', 'pdf']),
        required=False,
        default="pdf",
        description="Do you want the output to be bokeh plots in html (option = 'html') or pdf files for plots (option = 'pdf', default)")
    

class RoughQCOutputSchema(argschema.schemas.DefaultSchema):
    iou_plot = OutputFile(
        required=True,
        description="Pdf/html file showing IOU plots")
    distortion_plot = OutputFile(
        required=True,
        description="Pdf/html file with distortion plots")
    
