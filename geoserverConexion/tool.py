import os
import sys
from zipfile import ZipFile
import glob
import shutil
from geoserver.catalog import Catalog
from geoserver.resource import Coverage
from geoserver.support import DimensionInfo


class GeoserverClient(object):

    url = ''
    user = ''
    pwd = ''
    catalog = None
    workspace = None
    workspace_name = ''

    def __init__(self, url, user, pwd):
        self.url = url
        self.user = user
        self.pwd = pwd
        self.catalog = None
        self.workspace = None
        self.workspace_name = ''

    def connect(self):
        try:
            self.catalog = Catalog(
                self.url, username=self.user, password=self.pwd)
            print("connected to Geoserver")
        except Exception as err:
            error = str(err).split()[50:61]
            print(" ".join(error))

    def get_workspace(self, name):
        if self.catalog:
            self.workspace = self.catalog.get_workspace(name)
            self.workspace_name = name
            print("Workspace found")
        else:
            print("Workspace not available")
            sys.exit()

    def get_store(self, store_name):
        if self.workspace:
            """
            store = self.catalog.get_store(store_name, self.workspace)
            if store:
                print("Store found")
                return store
            else:
                print("Store not found:", store_name)
                return None
            """
            try:
                store = self.catalog.get_store(store_name, self.workspace)
                return store
            except Exception as err:
                print("Store not found:", store_name)
                return None
        else:
            print("Workspace not found:", store_name)
            return None
        
    def get_stores(self):
        if self.workspace:
            try:
                stores = self.catalog.get_stores(self.workspace)
                return stores
            except Exception as err:
                print("Stores not found in:", self.workspace)
                return None

    def zip_files(self, folder, folder_properties, folder_tmp, zip_path):
        if os.path.exists(folder) and os.path.exists(folder_properties):

            if os.path.exists(folder_tmp):
                shutil. rmtree(folder_tmp)
            os.mkdir(folder_tmp)

            # Copying files
            props = glob.glob(os.path.join(folder_properties, '*.properties'))
            if len(props) != 2:
                print("check the properties file")
                sys.exit()
            for p in props:
                f = p.rsplit(os.path.sep, 1)[-1]
                print("Copying properties")
                shutil.copyfile(p, os.path.join(folder_tmp, f))

            # Copying rasters
            files = glob.glob(os.path.join(folder, "*.*"))
            for file in files:
                f = file.rsplit(os.path.sep, 1)[-1]
                shutil.copyfile(file, os.path.join(folder_tmp, f))

            zip_name = "mosaic.zip"  # zip file name
            list_files = glob.glob(os.path.join(folder_tmp, "*.*"))
            zip = ZipFile(os.path.join(zip_path, zip_name), mode="w")
            print("Zipping")
            for f in list_files:
                zip.write(f, f.rsplit(os.path.sep, 1)[-1])
            zip.close()
            zip_path = os.path.join(zip_path, zip_name)
            print("zip:",zip_path)
            return zip_path
        else:
            print("Not zipped")
            print(folder, os.path.exists(folder))
            print(folder_properties, os.path.exists(folder_properties))
            return None

    def create_mosaic(self, store_name, file, folder_properties, folder_tmp, zip_path):
        output = self.zip_files(file, folder_properties, folder_tmp, zip_path)
        #print(output)
        self.catalog.create_imagemosaic(store_name, output, workspace=self.workspace)
        print(f"Mosaic store : {store_name} is created!")
        store = self.catalog.get_store(store_name, workspace=self.workspace)
        url = self.url + "workspaces/" + self.workspace_name + \
            "/coveragestores/" + store_name + "/coverages/" + store_name + ".xml"
        print(url)
        xml = self.catalog.get_xml(url)
        name = xml.find("name").text
        coverage = Coverage(self.catalog, store=store,
                            name=name, href=url, workspace=self.workspace)
        print("Get resource success")
        # defined coverage type for this store geotiff
        coverage.supported_formats = ["GEOTIFF"]
        # enable the time dimension
        timeInfo = DimensionInfo(name="time", enabled="true", presentation="LIST", resolution=None,
                                 units="ISO8601", unit_symbol=None)
        coverage.metadata = {
            "dirName": "f{store_name}_{store_name}", "time": timeInfo}
        self.catalog.save(coverage)
        # add style to the layer created
        # layer=cat.get_layer(store_name)
        # style=cat.get_style(style_name)
        # layer.default_style=style
        # cat.save(layer)
        print("Time Dimension is enabled")
        print("Done Successfully!")

    def update_mosaic(self, store, file, folder_properties, folder_tmp, zip_path):
        output = self.zip_files(file, folder_properties, folder_tmp, zip_path)
        self.catalog.harvest_uploadgranule(output, store)
        print("Mosaic updated")

    def check(self, store):
        coverages = self.catalog.mosaic_coverages(store)
        granules = self.catalog.mosaic_granules(
            (coverages[b"coverages"][b"coverage"][0][b"name"]).decode("utf-8"), store)
        granules_count = len(granules[b"features"])
        print("granules", granules_count)

    def delete_folder_content(self, folder_path):
        list_dir = os.listdir(folder_path)
        for filename in list_dir:
            file_path = os.path.join(folder_path, filename)

            if os.path.isfile(file_path) or os.path.islink(file_path):
                print("deleting file:", file_path)
                os.unlink(file_path)

            elif os.path.isdir(file_path):
                print("deleting folder:", file_path)
                shutil.rmtree(file_path)