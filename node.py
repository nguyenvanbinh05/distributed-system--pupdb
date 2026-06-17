import os, sys, argparse, json
from flask import Flask, request, jsonify
from pupdb.core import PupDB

app = Flask(__name__)

# Quét tham số --port từ dòng lệnh (Fix lỗi ValueError)
parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=5001)
args, unknown = parser.parse_known_args()
PORT = args.port

app.config['PORT'] = PORT
db_path = f'db_node_{PORT}.json'
db = PupDB(db_path)

@app.route('/set', methods=['POST'])
def set_data():
    data = request.json
    try:
        db.set(data['key'], data['value'])
        return jsonify({"status": "success", "message": f"Lưu tại {PORT}"})
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get', methods=['GET'])
def get_data():
    key = request.args.get('key')
    try:
        value = db.get(key)
        if value is not None:
            return jsonify({"status": "success", "value": value, "node": PORT})
        return jsonify({"status": "not_found", "node": PORT}), 404
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)})
    
@app.route('/delete', methods=['POST'])
def delete_data():
    try:
        db.remove(request.json['key']) 
        return jsonify({"status": "success"})
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get_all', methods=['GET'])
def get_all():
    try:
        with open(db_path, 'r') as f: data = json.load(f)
        return jsonify({"status": "success", "keys": list(data.keys()), "node": PORT})
    except: 
        return jsonify({"status": "error", "keys": []})

if __name__ == '__main__':
    print(f"🚀 Storage Node đang chạy tại Port {PORT}...")
    app.run(port=PORT, debug=False, use_reloader=False)