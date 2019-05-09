# imports needed for rough_align_qc
import os
import matplotlib as mpl
if os.environ.get('DISPLAY', '') == '':
    mpl.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402,F401
import mpld3  # noqa: E402,F401
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402,F401
from descartes.patch import PolygonPatch  # noqa: E402,F401
