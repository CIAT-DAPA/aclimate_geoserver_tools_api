from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from io import BytesIO

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

    return send_file(BytesIO(result), mimetype='image/tiff')


if __name__ == '__main__':
    app.run(debug=True)
