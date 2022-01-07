[![Docs](https://readthedocs.org/projects/render-modules/badge/)](https://readthedocs.org/projects/asap-modules)
[![Code cov](https://codecov.io/gh/AllenInstitute/asap-modules/branch/master/graph/badge.svg?token=nCNsugRDky)](https://codecov.io/gh/AllenInstitute/asap-modules)

# ASAP-modules

Shared repo for EM connectomics and Array Tomography render based image processing modules 

# Installation


## Prerequisites


ASAP requires Render web service (https://github.com/saalfeldlab/render) to be installed for storing and processing the data. 
Please refer to [Render](https://github.com/saalfeldlab/render) for details on its installation.

## Installing ASAP-modules


ASAP can be installed using the following commands.

1. Clone this repository

```
# git clone this repository
git clone https://github.com/AllenInstitute/asap-modules .
```

### Pip installation

2. CD to the cloned directory and run setup.py

```
python setup.py install 
```

### Docker setup

```
docker build -t asap-modules:latest --target asap-modules .
```

### Running docker

```
docker run --rm asap-modules:latest
```


3. Once ASAP is installed using the above command, you can use all of its functionalities as follows;

```python
python -m asap.<submodule>.<function_to_run> --input_json <input_json_file.json> --output_json <output_json_file.json>
```

For example, the montage qc module can be run using the following command.

```python
python -m asap.em_montage_qc.detect_montage_defects --input_json <your_input_json_file_with_required_parameters> --output_json <output_json_file_with_full_path>
```

and here is an example input json file for the detect_montage_defects module

```json
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
```
The list of parameters required for each module can be found out using the --help option. 

```python
# find the list of parameters for the solver module using its help option
python -m asap.solver.solve --help
```


# How to run

The order of processing is as follows;
1. [Lens distortion correction](https://github.com/AllenInstitute/asap-modules/blob/docs/docs/readme/lens_correction.md)
2. [Mipmap generation](https://github.com/AllenInstitute/asap-modules/blob/docs/docs/readme/mipmaps.md)
3. [Montaging and Montage QC](https://github.com/AllenInstitute/asap-modules/blob/docs/docs/readme/montaging.md)
4. [Global 3D non-linear alignment](https://github.com/AllenInstitute/asap-modules/blob/docs/docs/readme/rough_alignment.md)


# Other Modules 

A few other modules are included in ASAP to do the following.

1. Materialization - render intermediate/final aligned volume to disk for further processing
2. Fusion - Fuse global 3D non-linear aligned chunks together to make a complete volume
3. Point match filter - A module that performs point match filtering of an existing point match collection
4. Point match optimization - Performs a parameter sweep from a given set of ranges on a random sample of tilepairs to identify the optimal set of parameters
5. Registration - Register individual sections in an already aligned volume (useful in cases of aligning missing/reimaged sections)


# Support

We are not currently supporting this code, but simply releasing it to the community AS IS but are not able to provide any guarantees of support, as it is under active development. The community is welcome to submit issues, but you should not expect an active response.

# Acknowledgments

This project is supported by the Intelligence Advanced Research Projects Activity (IARPA) via Department of Interior / Interior Business Center (DoI/IBC) contract number D16PC00004. The U.S. Government is authorized to reproduce and distribute reprints for Governmental purposes notwithstanding any copyright annotation theron.

Disclaimer: The views and conclusions contained herein are those of the authors and should not be interpreted as necessarily representing the official policies or endorsements, either expressed or implied, of IARPA, DoI/IBC, or the U.S. Government.
