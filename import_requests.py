import requests
import rasterio
import numpy as np
from urllib.parse import urlencode
from rasterio.io import MemoryFile


class Response:
    def __init__(self, image=None, error=None):
        self.image = image
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
    subtraction = raster1_array - raster2_array

    # Convert NaN values back to -9999
    subtraction[np.isnan(subtraction)] = -9999

    return subtraction

def main(years, month, user, passw):

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

    climatology_norm = np.linalg.norm(climatology)

    # Normalizar la matriz subtraction
    normalized_subtraction = np.where(subtraction != -9999, subtraction / climatology_norm, -9999)

    # valores_filtrados = subtraction[subtraction != -9999]

    # # Obtener el mínimo de los valores filtrados
    # minimo = np.min(valores_filtrados)
    # print(minimo)
    with MemoryFile() as memfile:
        with memfile.open(driver='GTiff', width=normalized_subtraction.shape[1], height=normalized_subtraction.shape[0], count=1, dtype=subtraction.dtype, crs=spatial_info['crs'], transform=spatial_info['transform']) as dataset:
            dataset.write(normalized_subtraction, 1)
        memfile.seek(0)
        geojson_result = memfile.read()
    #geojson_result = convert_to_geojson(subtraction, spatial_info)

    return Response(image=geojson_result)
  
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

      return Response(image=mean_value)
    except Exception as e:
      # Si ocurre un error, configura el error en el objeto Response
      return Response(error=str(e))
