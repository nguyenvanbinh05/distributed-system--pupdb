import os
import argparse
from flask import Flask, request, jsonify
from pupdb.core import PupDB

app = Flask(__name__)
db = None  
db_path = ""

@app.route('/set', methods=['POST'])
def set_data():
    data = request.json
    try:
        db.set(data['key'], data['value'])
        return jsonify({"status": "success", "message": f"Lưu tại {app.config['PORT']}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get', methods=['GET'])
def get_data():
    key = request.args.get('key')
    try:
        value = db.get(key)
        if value is not None:
            return jsonify({"status": "success", "value": value, "node": app.config['PORT']})
        return jsonify({"status": "not_found", "node": app.config['PORT']})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    
@app.route('/delete', methods=['POST'])
def delete_data():
    data = request.json
    try:
        db.remove(data['key']) 
        return jsonify({"status": "success", "message": f"Đã xóa khỏi {app.config['PORT']}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get_all', methods=['GET'])
def get_all():
    try:
        with open(db_path, 'r') as f:
            import json
            data = json.load(f)
        return jsonify({"status": "success", "keys": list(data.keys()), "node": app.config['PORT']})
    except: return jsonify({"status": "error", "keys": []})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    app.config['PORT'] = args.port
    db_path = f'db_node_{args.port}.json'
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        with open(db_path, 'w') as f: f.write('{}')
    db = PupDB(db_path) 
    app.run(host='0.0.0.0', port=args.port, debug=False)