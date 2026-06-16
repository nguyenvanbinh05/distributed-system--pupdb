from flask import Flask, render_template
from routes.api import api_bp, hash_ring 

app = Flask(__name__)
app.register_blueprint(api_bp)

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    # Kiểm tra xem hash_ring đã có node chưa, nếu chưa mới thêm
    if not hash_ring.all_nodes_ui:
        hash_ring.add_node("http://127.0.0.1:5001")
        hash_ring.add_node("http://127.0.0.1:5002")
        hash_ring.add_node("http://127.0.0.1:5003")
    app.run(port=8000, debug=True)