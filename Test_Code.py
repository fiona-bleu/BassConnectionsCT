## Test code for Year of Installation
#import the necessary libraries
import os  
import geopandas as gpd  # for .shp data
import rasterio  # for .tif files
from rasterio.warp import calculate_default_transform, reproject, Resampling  # for reprojection
import pandas as pd  # for CSV
import dash  # for interactive web app
from dash import dcc, html  # dash components
from dash.dependencies import Input, Output  # managing app interactivity
import plotly.express as px  # for visualizing raster data
import numpy as np  # for numerical operations

# Directory to save reprojected rasters
reprojected_dir = "Z:/BassConnectionsCT/Reprojected_Images"  # Adjust this path as needed
os.makedirs(reprojected_dir, exist_ok=True)  # Create the directory if it doesn't exist

# locate data folder 
data_folder = "Z:/BassConnectionsCT/Test_Images"  # Replace with your own path

# load the .shp file 
shp_file = [f for f in os.listdir(data_folder) if f.endswith(".shp")]
if len(shp_file) != 1:
    raise ValueError("There must be exactly one .shp file in the folder!")
shp_path = os.path.join(data_folder, shp_file[0])

# load the shapefile into a geodataframe
gdf = gpd.read_file(shp_path)
print("Loaded shapefile:", shp_path)

# CRS of the shapefile
target_crs = gdf.crs
print("Shapefile CRS:", target_crs)

# list all .tif files in the folder
tif_files = [os.path.join(data_folder, f) for f in os.listdir(data_folder) if f.endswith(".tif")]
if not tif_files:
    raise ValueError("No .tif files found in the folder!")
print("Loaded .tif files:", tif_files)

# Reproject the rasters to match the shapefile CRS
reprojected_tif_files = []  # List to store reprojected raster paths
for tif_path in tif_files:
    with rasterio.open(tif_path) as src:
        # Check if CRS matches
        if src.crs != target_crs:
            print(f"Reprojecting {tif_path} to match shapefile CRS...")
            # Calculate transform and dimensions for target CRS
            transform, width, height = calculate_default_transform(
                src.crs, target_crs, src.width, src.height, *src.bounds
            )
            # Update metadata for the reprojected raster
            kwargs = src.meta.copy()
            kwargs.update({
                "crs": target_crs,
                "transform": transform,
                "width": width,
                "height": height
            })
            # Define the output file path
            output_path = os.path.join(reprojected_dir, os.path.basename(tif_path))
            reprojected_tif_files.append(output_path)
            # Perform reprojection
            with rasterio.open(output_path, "w", **kwargs) as dst:
                for i in range(1, src.count + 1):  # Reproject each band
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=target_crs,
                        resampling=Resampling.nearest
                    )
        else:
            print(f"{tif_path} already matches shapefile CRS.")
            reprojected_tif_files.append(tif_path)  # Add original file if CRS matches

# Update tif_files to use reprojected rasters
tif_files = reprojected_tif_files
print("Reprojection complete. Using reprojected .tif files.")

# Extract polygons from the shapefile
polygons = gdf.geometry  
print(f"Loaded {len(polygons)} polygons.")

# Create a results DF to store user selections
results = pd.DataFrame({"Polygon_ID": gdf.index, "First_Year": None})
print("Initialized results storage.")

# Initialize web app
app = dash.Dash(__name__)

# Define the app layout (UI components)
app.layout = html.Div([
    # Navigation buttons for cycling through polygons
    html.Div([
        html.Button("Previous", id="prev-button", n_clicks=0),
        html.Button("Next", id="next-button", n_clicks=0),
        dcc.Dropdown(
            id="year-dropdown",
            options=[{"label": os.path.basename(f).split('_')[0], "value": os.path.basename(f).split('_')[0]} for f in tif_files],
            placeholder="Select first installation year"
        ),
        html.Button("Save Selection", id="save-button", n_clicks=0),
    ]),
    # Placeholder for polygon information and raster images
    html.Div(id="polygon-info"),
    html.Div(id="image-display"),
    html.Div(id="results-output"),
])

# Track the current polygon index
selected_polygon_idx = [0]  # Mutable list to allow updates

# Callback to update the displayed polygon
@app.callback(
    [Output("polygon-info", "children"), Output("image-display", "children")],
    [Input("prev-button", "n_clicks"), Input("next-button", "n_clicks")]
)
def update_polygon(prev_clicks, next_clicks):
    # Update the current polygon index
    idx = selected_polygon_idx[0]
    idx = max(0, min(len(polygons) - 1, idx + (next_clicks - prev_clicks)))
    selected_polygon_idx[0] = idx

    # Get the current polygon and its centroid
    current_polygon = polygons.iloc[idx]
    centroid = current_polygon.centroid
    buffer_size = 50  # Buffer size in raster units (adjust as needed)

    # Prepare the images for display
    images = []
    for tif_path in tif_files:
        with rasterio.open(tif_path) as src:
            # Get raster indices around the centroid with buffer
            row, col = src.index(centroid.x, centroid.y)
            window = rasterio.windows.Window(
                col_off=max(0, col - buffer_size),
                row_off=max(0, row - buffer_size),
                width=buffer_size * 2,
                height=buffer_size * 2,
            )

            # Read raster data from the buffered window
            image_data = src.read([1, 2, 3], window=window, boundless=True, fill_value=0)
            image_data = np.moveaxis(image_data, 0, -1)  # Reorder for plotting

            # Create a Plotly figure
            fig = px.imshow(
                image_data,
                title=os.path.basename(tif_path),
                aspect="auto"
            )
            images.append(dcc.Graph(figure=fig))

    return f"Polygon {idx + 1}/{len(polygons)}", images

# Callback to save the selected year
@app.callback(
    Output("results-output", "children"),
    [Input("save-button", "n_clicks")],
    [dash.dependencies.State("year-dropdown", "value")]
)
def save_selection(save_clicks, selected_year):
    if selected_year is not None:
        idx = selected_polygon_idx[0]
        results.loc[idx, "First_Year"] = selected_year
        return f"Saved: Polygon {idx + 1} -> {selected_year}"
    return "No selection made."

if __name__ == "__main__":
    app.run_server(debug=True)