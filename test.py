import matplotlib.pyplot as plt
import numpy as np

ax = np.array((2,2), dtype='object')
fig, ax = plt.subplots(2,2)
print(ax)
print(ax.shape)
print(type(ax))
print(ax[0,0])
