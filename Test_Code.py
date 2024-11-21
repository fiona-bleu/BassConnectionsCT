## Test code for Year of Installation
#import the necessary libraries
import os  
import geopandas as gpd  # for .shp data
import rasterio  # for .tif files
import pandas as pd  # for CSV
import dash  # for interactive web app
from dash import dcc, html  # dash components
from dash.dependencies import Input, Output  # managing app interactivity
import plotly.express as px  # for visualizing raster data
import numpy as np  # for numerical operations

# locate data folder 
data_folder = "Z:/BassConnectionsCT/Test_Images" ## replace with own path to folder ##

# load the .shp file 
shp_file = [f for f in os.listdir(data_folder) if f.endswith(".shp")]
if len(shp_file) != 1:
    raise ValueError("There must be exactly one .shp file in the folder!")
shp_path = os.path.join(data_folder, shp_file[0])

#load the shapefile into a geodataframe
gdf = gpd.read_file(shp_path)
print("Loaded shapefile:", shp_path)

#list all .tif files in the folder
tif_files = [os.path.join(data_folder, f) for f in os.listdir(data_folder) if f.endswith(".tif")]
if not tif_files:
    raise ValueError("No .tif files found in the folder!")
print("Loaded .tif files:", tif_files)
