from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# imports needed for rough_align_qc
import os
import matplotlib as mpl
if os.environ.get('DISPLAY', '') == '':
    mpl.use('Agg')

import matplotlib.pyplot as plt
import mpld3
from matplotlib.backends.backend_pdf import PdfPages
from descartes.patch import PolygonPatch