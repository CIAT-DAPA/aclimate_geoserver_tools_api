import requests
import rasterio
import numpy as np
from urllib.parse import urlencode
from rasterio.io import MemoryFile
from rasterio.mask import mask
import geopandas as gpd
import os
import json
import shutil
import re
from geoserverConexion.geoserver import GeoserverImport 

class Response:
    def __init__(self, res=None, error=None):
        self.res = res
        self.error = error


def convert_to_geojson(subtraction_array, spatial_info):
    # Obtener la transformación espacial (affine transformation) del archivo GeoTIFF
    transform = spatial_info['transform']
    
    # Obtener la resolución espacial
    x_resolution = transform.a
    y_resolution = -transform.e  # Negativo porque la transformación mantiene el eje Y invertido
    
    # Obtener la esquina superior izquierda
    x_origin = transform.c
    y_origin = transform.f
    
    # Crear una lista para almacenar las geometrías y propiedades de los polígonos
    features = []
    
    # Obtener la forma de la matriz de resta
    rows, cols = subtraction_array.shape
    
    # Iterar sobre cada celda de la matriz de resta
    for row in range(rows):
        for col in range(cols):
            # Obtener el valor de la celda
            value = float(subtraction_array[row, col])
            
            # Calcular las coordenadas geográficas de la celda
            lon = x_origin + col * x_resolution
            lat = y_origin + row * y_resolution
            
            # Crear un polígono cuadrado con la esquina superior izquierda y la esquina inferior derecha de la celda
            geometry = {
                "type": "Polygon",
                "coordinates": [
                    [
                        [lon, lat],
                        [lon + x_resolution, lat],
                        [lon + x_resolution, lat - y_resolution],
                        [lon, lat - y_resolution],
                        [lon, lat]
                    ]
                ]
            }
            
            # Crear una propiedad con el valor de la celda
            properties = {
                "value": value
            }
            
            # Crear una característica GeoJSON con la geometría y las propiedades
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": properties
            }
            
            # Agregar la característica a la lista de características
            features.append(feature)
    
    # Crear el objeto GeoJSON final
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    return geojson


def calculate_average(rasters):
    raster_arrays = [rasterio.open(raster).read(1) for raster in rasters]
    average = np.mean(raster_arrays, axis=0)
    return average

def subtract_rasters(raster1, raster2):
    # Convert rasters to NumPy arrays and ensure they are of float type to handle -9999 values correctly
    raster1_array = np.array(raster1, dtype=np.float32)
    raster2_array = np.array(raster2, dtype=np.float32)

    # Mask -9999 values to prevent them from affecting subtraction
    raster1_array[raster1_array == -9999] = np.nan
    raster2_array[raster2_array == -9999] = np.nan

    # Perform subtraction and keep values as NaN when one of the values is NaN
    subtraction = ((raster1_array - raster2_array) / raster2_array) * 100

    # Convert NaN values back to -9999
    subtraction[np.isnan(subtraction)] = -9999

    return subtraction

def main(years, month, user, passw, anomalie=True):

  try:
    spatial_info = None
    all_raster_arrays = []

    url_root = "https://geo.aclimate.org/geoserver/"
    workspace = "historical_climate_hn"
    workspaceC = "climatology_hn"
    mosaic_name = "PREC"
    urls = []

    for year in years:
        base_url = f"{url_root}{workspace}/ows?"
        params = {
            "service": "WCS",
            "request": "GetCoverage",
            "version": "2.0.1",
            "coverageId": mosaic_name,
            "format": "image/geotiff",
            "subset": f"Time(\"{year}-{month:02d}-01T00:00:00.000Z\")"
        }
        url = base_url + urlencode(params)
        urls.append(url)

        response = requests.get(url, auth=(user, passw))
        # If response is 404, nothing found, break out of loop
        if response.status_code == 404:
            break
        
        # Open response content with rasterio
        with MemoryFile(response.content) as memfile:
            with memfile.open() as raster:
                raster_array = raster.read(1)
                all_raster_arrays.append(raster_array)
                spatial_info = raster.profile  # Get spatial info in here
        
    
    if not all_raster_arrays:
        print("No rasters found for download.")
        return
    
    # Calculate average of rasters
    average_array = np.mean(all_raster_arrays, axis=0)
    
    if anomalie:
        base_url = f"{url_root}{workspaceC}/ows?"
        params = {
            "service": "WCS",
            "request": "GetCoverage",
            "version": "2.0.1",
            "coverageId": mosaic_name,
            "format": "image/geotiff",
            "subset": f"Time(\"2000-{month:02d}-01T00:00:00.000Z\")"
        }
        url = base_url + urlencode(params)
        urls.append(url)

        responseC = requests.get(url, auth=(user, passw))


        
        climatology = None

        with MemoryFile(responseC.content) as memfile:
                with memfile.open() as raster:
                    raster_array = raster.read(1)
                    climatology = raster_array


        subtraction = subtract_rasters(average_array, climatology)

        
        with MemoryFile() as memfile:
            with memfile.open(driver='GTiff', width=subtraction.shape[1], height=subtraction.shape[0], count=1, dtype=subtraction.dtype, crs=spatial_info['crs'], transform=spatial_info['transform']) as dataset:
                dataset.write(subtraction, 1)
            memfile.seek(0)
            geojson_result = memfile.read()
        #geojson_result = convert_to_geojson(subtraction, spatial_info)

        return Response(res=geojson_result)
    else:
        with MemoryFile() as memfile:
            with memfile.open(driver='GTiff', width=average_array.shape[1], height=average_array.shape[0], count=1, dtype=average_array.dtype, crs=spatial_info['crs'], transform=spatial_info['transform']) as dataset:
                dataset.write(average_array, 1)
            memfile.seek(0)
            geojson_result = memfile.read()
        #geojson_result = convert_to_geojson(subtraction, spatial_info)

        return Response(res=geojson_result)
  
  except Exception as e:
      # Si ocurre un error, configura el error en el objeto Response
      return Response(error=str(e))



def calculate_mean(workspace, mosaic_name, year, month, user, passw):
    
    try:
      url_root = "https://geo.aclimate.org/geoserver/"
      base_url = f"{url_root}{workspace}/ows?"
      params = {
          "service": "WCS",
          "request": "GetCoverage",
          "version": "2.0.1",
          "coverageId": mosaic_name,
          "format": "image/geotiff",
          "subset": f"Time(\"{year:04d}-{month:02d}-01T00:00:00.000Z\")"
      }
      url = base_url + urlencode(params)
      response = requests.get(url, auth=(user, passw))
      mean_value = None
      with MemoryFile(response.content) as memfile:
          with memfile.open() as dataset:
              raster_array = dataset.read(1)
              raster_array = raster_array.astype(np.float64)
              masked_array = np.ma.masked_where(raster_array == np.min(raster_array), raster_array)
              
              mean_value = np.mean(masked_array)

      return Response(res=mean_value)
    except Exception as e:
      # Si ocurre un error, configura el error en el objeto Response
      return Response(error=str(e))
    

def getDataPerRegion(workspace, stores, dates, user, passw, shp_workspace, shp_store):
    try:

      url_root = "https://geo.aclimate.org/geoserver/"
      base_url = f"{url_root}{workspace}/ows?"
      base_url_shp = f"{url_root}{shp_workspace}/ows?"

      params = {
        "service": "WFS",
        "request": "GetFeature",
        "version": "1.0.0",
        "typeName": shp_workspace+":"+shp_store,
        "outputFormat": "application/json",
        "maxFeatures": 50,
        "src": "EPSG:4326"
      } 
      url = base_url_shp + urlencode(params)
      response = requests.get(url, auth=(user, passw))


      shapefile = json.loads(response.content)
      

      results = {}

      for geometry in shapefile['features']:
          department = geometry["properties"]["ADM1_EN"]
          department_data = {}
          for i, date in enumerate(dates, start=1):
              season_data = {}
              
              # Iterate over each store
              for store in stores:
                  # Get the raster corresponding to the store and date
                  params = {
                      "service": "WCS",
                      "request": "GetCoverage",
                      "version": "2.0.1",
                      "coverageId": store,
                      "format": "image/geotiff",
                      "subset": f"Time(\"{date[0]:04d}-{date[1]:02d}-01T00:00:00.000Z\")"
                  }
                  url = base_url + urlencode(params)
                  response = requests.get(url, auth=(user, passw))
                  
                  # Mask the raster with the current geometry
                  with MemoryFile(response.content) as memfile:
                      with memfile.open() as raster:
                          try:
                              out_image, _ = mask(raster, [geometry['geometry']], crop=True)
                              masked_out_image = np.ma.masked_where(out_image < 0, out_image)
                              average_without_min = masked_out_image.mean()

                              if np.ma.is_masked(average_without_min):
                                  average_without_min = "Null"
                              else:
                                  average_without_min = float(average_without_min)
                              
                              season_data[store] = average_without_min
                          except Exception as e:
                              print(f"Error masking raster for store '{store}' on date '{date}': {e}")
              
              department_data[f"season_{i}"] = season_data
          
          results[department] = department_data
      json_results = json.dumps(results, indent=4)

      return Response(res=json_results)
    except Exception as e:
      print(e)
      return Response(error=str(e))
      

        

      
def importGeoserver(workspace, user, passw, geo_url, store, tiff):
    try:
        root_path  = os.path.dirname(os.path.realpath(__file__))

        patron = r'^.+_\d{6}\.tif$'

   
        regex = re.compile(patron)

        if not regex.match(tiff.filename):
            return Response(error="El nombre no coincide con el patron filename_YYYYmm.tif")

        geoserver_path= os.path.join(root_path, "geoserverConexion")
        layer_path= os.path.join(geoserver_path, "layers")
        zip_path= os.path.join(geoserver_path, "zip")
        tmp_path= os.path.join(geoserver_path, "tmp")
        store_path= os.path.join(layer_path, store)
        os.makedirs(store_path, exist_ok=True)
        os.makedirs(tmp_path, exist_ok=True)
        os.makedirs(zip_path, exist_ok=True)
        tiff.save(os.path.join(store_path, tiff.filename))
        geoserver = GeoserverImport(workspace, user, passw, geo_url)
        result = geoserver.connect_geoserver()
        shutil.rmtree(store_path)
        shutil.rmtree(tmp_path)
        shutil.rmtree(zip_path)
        if not result:
            return Response(error="Error al guardar")

        return Response(res="Se guardo correctamente")
    except Exception as e:
      return Response(error=str(e))
    


def getGeoserverStores(workspace, user, passw, geo_url):
    try:
        geoserver = GeoserverImport(workspace, user, passw, geo_url)
        stores = geoserver.get_geoserver_stores()
        store_names = [store.name for store in stores]
        return Response(res=store_names)
    except Exception as e:
      print(e)
      return Response(error=str(e))


#importGeoserver("fc_analogues_hn", "scalderon", "Santi2711.", "https://geo.aclimate.org/geoserver/rest/", "above", "aa")