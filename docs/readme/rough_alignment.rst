.. _rough-alignment:

Global 3D non-linear alignment
###############################

Global 3D non-linear alignment can be performed on a stack in chunks as
well as the entire dataset (if all the serial sections are montaged and
available). The following steps illustrate the global 3D non-linear
alignment process.

Step 1 - Montage scapes generation
===================================

Montage scapes are downsampled versions of the serial sections and are
used in the global 3D alignment process. Montage scapes can be generated
as follows.

::

   # Generate downsampled versions of montaged serial sections
   python -m asapmodules.materialize.render_downsample_sections --input_json <input_parameter_json_file> --output_json <output_json_file>

::

   # Create a downsampled montage stack
   python -m asapmodules.dataimport.make_montage_scapes_stack --input_json <input_parameter_json_file> --output_json <output_json_file>

Step 2 - Generate tilepairs
============================

3D tilepairs for the downsampled stack can be generated using the
following command.

::

   python -m asapmodules.pointmatch.create_tilepairs --input_json <input_parameter_json_file> --output_json <output_json_file>

Step 3 - Generate point matches
================================

3D point matches can be generated using the generated tile pairs. The
following command can be used to generate point matches using a Spark
cluster

::

   python -m asapmodules.pointmatch.generate_point_matches_using_spark --input_json <input_parameter_json_file> --output_json <output_json_file>

Step 4 - Solve for 3D non-linear transformations
=================================================

This step in practice is done as a multi-step 3D alignment process,
where a series of transformations (rigid, affine, non-linear) are
computed and used as initialization for the computation of next higher
order transformation.

A mesh based alignment can also be applied as a last step and is
available in `Bigfeta <https://github.com/AllenInstitute/bigfeta>`__.

The command to run the solver is shown below.

::

   python -m asapmodules.solver.solve --input_json <input_parameter_json_file> --output_json <output_json_file>

NOTE: Each of the modules’ script include an example input json file for
reference and the list of input and output parameters can also be listed
using the –help option in each of the above commands.
