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
    user = data.get('user')
    passw = data.get('passw')
    if not years or not month or not user or not passw:
        return jsonify({'error': 'The array of years and the month are required.'}), 400
    result = main(years, month, user, passw)
    
    if result.error:
        return jsonify({'error': result.error}), 400
    else:
        return send_file(BytesIO(result.image), mimetype='image/tiff')


if __name__ == '__main__':
    app.run(debug=True)
