from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from io import BytesIO

from import_requests import main, calculate_mean, getDataPerRegion

app = Flask(__name__)
CORS(app)


@app.route('/api/subtract_rasters', methods=['POST'])
def calculate_subtraction():
    data = request.json
    years = data.get('years')
    month = data.get('month')
    user = data.get('user')
    passw = data.get('passw')
    if not years or not month or not user or not passw:
        return jsonify({'error': 'The array of years and the month are required.'}), 400
    result = main(years, month, user, passw)

    if result.error:
        return jsonify({'error': result.error}), 400
    else:
        return send_file(BytesIO(result.image), mimetype='image/tiff')


@app.route('/api/global_average', methods=['POST'])
def calculate_average():
    data = request.json
    workspace = data.get('workspace')
    mosaic_name = data.get('mosaic_name')
    years = data.get('years')
    month = data.get('month')
    user = data.get('user')
    passw = data.get('passw')
    if not years or not month or not user or not passw or not workspace or not mosaic_name:
        return jsonify({'error': 'The array of years and the month are required.'}), 400
    result = calculate_mean(workspace, mosaic_name, years, month, user, passw)

    if result.error:
        return jsonify({'error': result.error}), 400
    else:
        return jsonify({'body': result.image}), 200
    

@app.route('/api/data_region', methods=['POST'])
def calculate_data_region():
    data = request.json
    workspace = data.get('workspace')
    stores = data.get('stores')
    shp_workspace = data.get('shp_workspace')
    shp_store = data.get('shp_store')
    dates = data.get('dates')
    user = data.get('user')
    passw = data.get('passw')
    if not dates or not user or not passw or not workspace or not stores or not shp_workspace or not shp_store:
        return jsonify({'error': 'The array of years and the month are required.'}), 400
    result = getDataPerRegion(workspace, stores, dates, user, passw, shp_workspace, shp_store)

    if result.error:
        return jsonify({'error': result.error}), 400
    else:
        return jsonify({'body': result.image}), 200


if __name__ == '__main__':
    app.run(debug=True)
