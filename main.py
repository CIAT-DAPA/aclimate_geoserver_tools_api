from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
from io import BytesIO
import base64

from import_requests import main

app = Flask(__name__)
CORS(app)


@app.route('/api/subtract_rasters', methods=['POST'])
def calculate_subtraction():
    data = request.json
    years = data.get('years')
    month = data.get('month')
    if not years or not month:
        return jsonify({'error': 'The array of years and the month are required.'}), 400
    result = main(years, month)

    # Devolver la cadena JSON en la respuesta Flask
    #geojson_string = json.dumps(result)
    #return jsonify(result), 200, {'Content-Type': 'application/json'}

    #Bytes
    return send_file(BytesIO(result), mimetype='image/tiff')

    # Codifica el contenido binario en Base64
    #tiff_base64 = base64.b64encode(result).decode("utf-8")
    # Devuelve el contenido codificado en Base64 en la respuesta JSON
    #return {"geoTiffData": tiff_base64}


if __name__ == '__main__':
    app.run(debug=True)
