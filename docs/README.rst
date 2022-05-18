|Docs| |Code cov|


ASAP-modules
############

ASAP is a set of modules to perform stitching and alignment of EM and Array tomography data.
It is suitable for processing large-scale datasets and supports multiple computational environments.

Installation
############

Please refer the documentation :ref:`Installation <installation>`. on how to install and use ASAP modules 

How to run
##########

The order of processing is as follows; 

1. :doc:`Lens distortion correction </readme/lens_correction>`

2. :doc:`Mipmap generation </readme/mipmaps>`

3. :doc:`Montaging and Montage QC </readme/montaging>`

4. :doc:`Global 3D non-linear alignment </readme/rough_alignment>`

Other Modules
#############

A few other modules are included in ASAP to do the following.

1. Materialization - render intermediate/final aligned volume to disk
   for further processing
2. Fusion - Fuse global 3D non-linear aligned chunks together to make a
   complete volume
3. Point match filter - A module that performs point match filtering of
   an existing point match collection
4. Point match optimization - Performs a parameter sweep from a given
   set of ranges on a random sample of tilepairs to identify the optimal
   set of parameters
5. Registration - Register individual sections in an already aligned
   volume (useful in cases of aligning missing/reimaged sections)

.. _support:
Support
########

We are planning on occasional updating this tool with no fixed schedule. 
Community involvement is encouraged through both issues and pull requests. 
Please make pull requests against the dev branch, as we will test changes 
there before merging into master.

.. _acknowledgements:
Acknowledgments
###############

This project is supported by the Intelligence Advanced Research Projects
Activity (IARPA) via Department of Interior / Interior Business Center
(DoI/IBC) contract number D16PC00004. The U.S. Government is authorized
to reproduce and distribute reprints for Governmental purposes
notwithstanding any copyright annotation theron.

Disclaimer: The views and conclusions contained herein are those of the
authors and should not be interpreted as necessarily representing the
official policies or endorsements, either expressed or implied, of
IARPA, DoI/IBC, or the U.S. Government.

.. |Docs| image:: https://readthedocs.org/projects/asap-modules/badge/
   :target: https://readthedocs.org/projects/asap-modules
.. |Code cov| image:: https://codecov.io/gh/AllenInstitute/asap-modules/branch/master/graph/badge.svg?token=nCNsugRDky
   :target: https://codecov.io/gh/AllenInstitute/asap-modules