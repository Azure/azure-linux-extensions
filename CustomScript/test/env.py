import sys
import os

#append installer directory to sys.path
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
installer = os.path.join(root, 'installer')
sys.path.append(installer)
