.. _installation:


Installation
############

Prerequisites
==============

ASAP requires Render web service (https://github.com/saalfeldlab/render)
to be installed for storing and processing the data. Please refer to
`Render <https://github.com/saalfeldlab/render>`__ for details on its
installation.

Installing ASAP-modules
=======================

ASAP can be installed using the following commands.

Clone this repository

::

   # git clone this repository
   git clone https://github.com/AllenInstitute/asap-modules .

Install from source
===================

CD to the cloned directory and run setup.py

::

   python setup.py install 

Docker setup
=============

 
You can also install asap-modules using the provided docker file

::

   docker build -t asap-modules:latest --target asap-modules .

Running docker
==============

The built docker image can then be run using the following command
::

   docker run --rm asap-modules:latest

Running modules of ASAP
========================

Once ASAP is installed using the above command, you can use all of 
its functionalities as follows;

.. code:: python

   python -m asap.<submodule>.<function_to_run> --input_json <input_json_file.json> --output_json <output_json_file.json>

For example, the montage qc module can be run using the following
command.

.. code:: python

   python -m asap.em_montage_qc.detect_montage_defects --input_json <your_input_json_file_with_required_parameters> --output_json <output_json_file_with_full_path>

and here is an example input json file for the detect_montage_defects
module

.. code:: json

   {
       "render":{
           "host": <render_host>,
           "port": <render_port>,
           "owner": <render_project_owner>,
           "project": <render_project_name>,
           "client_scripts": <path_to_render_client_scripts>
       },
       "prestitched_stack": <pre_montage_stack>,
       "poststitched_stack": <montaged_stack>,
       "match_collection_owner": <owner_of_point_match_collection>,
       "match_collection": <name_of_point_match_collection>,
       "out_html_dir": <path_to_directory_to_store_the_qc_plot_html_file>,
       "plot_sections": <True/False>,
       "minZ": <z_index_of_the_first_section_to_run_qc_for>,
       "maxZ": <z_index_of_the_last_section_to_run_qc_for>,
       "neighbors_distance": <qc_parameter>,
       "min_cluster_size": <qc_parameter>,
       "residual_threshold": <qc_parameter>,
       "pool_size": <pool_size_for_parallel_processing>
   }

The list of parameters required for each module can be found out using
the –help option.

.. code:: python

   # find the list of parameters for the solver module using its help option
   python -m asap.solver.solve --help
