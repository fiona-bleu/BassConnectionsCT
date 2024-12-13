## Year of Installation tool
#import the necessary libraries
import os  
import geopandas as gpd  #.shp data
import rasterio  #.tif files
from rasterio.warp import calculate_default_transform, reproject, Resampling  #for reprojection
import pandas as pd  #CSV
import dash  #interactive web app
from dash import dcc, html  #dash components
from dash.dependencies import Input, Output  #app interactivity
import plotly.express as px  #visualizing raster data
import numpy as np  #numerical operations
from shapely.geometry import box  #raster bounds as polygons

#create working directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

print(f"Working Directory Set to: {os.getcwd()}")

#locate data and creating reprojected rasters folder
data_folder = "./Test_Images"
reprojected_dir = "./Reprojected_Images" 
os.makedirs(reprojected_dir, exist_ok=True)

#load .shp file into geodataframe and determien CRS
shp_file = "./Test_Images/bolte.bradhurst_annotations_11.21.24.shp"
gdf = gpd.read_file(shp_file) 
gdf = gdf[gdf.geometry.notnull() & gdf.geometry.is_valid] #double check geometries
target_crs = gdf.crs
print("Shapefile CRS:", target_crs)

#reproject .tif files in the folder to .shp CRS
tif_files = [os.path.join(data_folder, f) for f in os.listdir(data_folder) if f.endswith(".tif")]
raster_bounds = [] 
reprojected_tif_files = []  #store reprojected raster paths

for tif_path in tif_files:
    with rasterio.open(tif_path) as src:
        #check CRS
        if src.crs != target_crs:
            print(f"Reprojecting {tif_path} to match shapefile CRS...")
            #transform and dimensions for target CRS
            transform, width, height = calculate_default_transform(
                src.crs, target_crs, src.width, src.height, *src.bounds
            )
            #update metadata 
            kwargs = src.meta.copy()
            kwargs.update({
                "crs": target_crs,
                "transform": transform,
                "width": width,
                "height": height
            })
            #define output file path
            output_path = os.path.join(reprojected_dir, os.path.basename(tif_path))
            reprojected_tif_files.append(output_path)
            #reprojection
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
            #bounds of the reprojected raster
            minx, miny = transform * (0, 0)
            maxx, maxy = transform * (width, height)
            raster_bounds.append(box(minx, miny, maxx, maxy))
        else:
            print(f"{tif_path} already matches shapefile CRS.")
            reprojected_tif_files.append(tif_path)
            raster_bounds.append(box(src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top))

tif_files = reprojected_tif_files
print("Reprojection complete")

#filter .shp polygons to match .tif extents
polygons = gpd.GeoSeries([p for p in gdf.geometry if any(p.intersects(r) for r in raster_bounds)], crs=gdf.crs)
print(f"Filtered {len(polygons)} polygons out of {len(gdf)}")

#initialize results
results = pd.DataFrame({"Polygon_ID": range(len(polygons)), "First_Year": None})

#initialize Dash web app
app = dash.Dash(name='YOI Tool')
app.layout = html.Div([
    #navigation buttons
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
    html.Div(id="polygon-info"),
    html.Div(id="image-display"),
    html.Div(id="results-output"),
])

#list for updated polygons
selected_polygon_idx = [0]

#callback to update the displayed polygon
@app.callback(
    [Output("polygon-info", "children"), Output("image-display", "children")],
    [Input("prev-button", "n_clicks"), Input("next-button", "n_clicks")]
)
def update_polygon(prev_clicks, next_clicks):
    #update current polygon index
    idx = selected_polygon_idx[0]
    idx = max(0, min(len(polygons) - 1, idx + (next_clicks - prev_clicks)))
    selected_polygon_idx[0] = idx

    #current polygon and its extent
    current_polygon = polygons.iloc[idx]
    extent = current_polygon.bounds 

    #load images for the current polygon
    images = []
    for tif_path in tif_files:
        with rasterio.open(tif_path) as src:
            try:
                window = src.window(*extent)
                image_data = src.read([1, 2, 3], window=window, boundless=True, fill_value=0)
                image_data = np.moveaxis(image_data, 0, -1)
                fig = px.imshow(image_data, title=os.path.basename(tif_path), aspect="auto")
                images.append(dcc.Graph(figure=fig))
            except ValueError:
                continue
    
    if not images:
        images.append(html.Div("No overlapping rasters for this polygon."))

    return f"Polygon {idx + 1}/{len(polygons)}", images

#save the selected year
@app.callback(Output("results-output", "children"),
    [Input("save-button", "n_clicks")],
    [dash.dependencies.State("year-dropdown", "value")]
)
def save_selection(save_clicks, selected_year):
    if selected_year is not None:
        idx = selected_polygon_idx[0]
        results.loc[idx, "First_Year"] = selected_year
        results_path = "./results.csv" #save to csv
        results.to_csv(results_path, index=False)
        return f"Saved: Polygon {idx + 1} -> {selected_year}. Results saved to results.csv"
    return "No selection made."

if __name__ == "__main__":
    app.run_server(debug=True)