from flask import Blueprint, request, jsonify
import hashlib, bisect, requests

api_bp = Blueprint('api', __name__)

class RealConsistentHashRing:
    def __init__(self):
        self.active_ring = {} 
        self.sorted_keys = [] 
        self.all_nodes_ui = {} 

    def _hash_to_angle(self, key):
        return int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16) % 360

    def add_node(self, node_url):
        if node_url not in self.all_nodes_ui:
            angle = self._hash_to_angle(node_url)
            while angle in [info['angle'] for info in self.all_nodes_ui.values()]: angle = (angle + 1) % 360
            self.all_nodes_ui[node_url] = {"angle": angle, "active": True}
            self._rebuild_ring()

    def toggle_node(self, node_url, force_state=None):
        if node_url in self.all_nodes_ui:
            if force_state is not None:
                self.all_nodes_ui[node_url]['active'] = force_state
            else:
                self.all_nodes_ui[node_url]['active'] = not self.all_nodes_ui[node_url]['active']
            self._rebuild_ring()

    def _rebuild_ring(self):
        self.active_ring = {info['angle']: url for url, info in self.all_nodes_ui.items() if info['active']}
        self.sorted_keys = sorted(self.active_ring.keys())

    def get_target_nodes(self, string_key, replicas=1):
        if not self.active_ring: return []
        angle = self._hash_to_angle(string_key)
        idx = bisect.bisect_right(self.sorted_keys, angle)
        if idx == len(self.sorted_keys): idx = 0
        nodes = []
        while len(nodes) < replicas and len(nodes) < len(self.active_ring):
            n = self.active_ring[self.sorted_keys[(idx + len(nodes)) % len(self.sorted_keys)]]
            if n not in nodes: nodes.append(n)
            else: break
        return nodes

hash_ring = RealConsistentHashRing()
stored_keys_info = {}

def rebalance_data():
    global stored_keys_info
    migrated_keys = 0
    for key, info in list(stored_keys_info.items()):
        old_replicas = info["replicas"]
        num_replicas = len(old_replicas) if old_replicas else 1
        
        new_targets = hash_ring.get_target_nodes(key, num_replicas)
        new_ports = [n.split(':')[-1] for n in new_targets]
        
        if set(old_replicas) != set(new_ports):
            value = None
            
            for port in old_replicas:
                url = f"http://127.0.0.1:{port}"
                if url in hash_ring.all_nodes_ui and hash_ring.all_nodes_ui[url]['active']:
                    try:
                        res = requests.get(f"{url}/get?key={key}", timeout=1.0).json()
                        if res.get('status') == 'success':
                            value = res['value']
                            break 
                    except: pass
            
            if value is not None:
                for target in new_targets:
                    target_port = target.split(':')[-1]
                    if target_port not in old_replicas: 
                        try: requests.post(f"{target}/set", json={"key": key, "value": value}, timeout=1.0)
                        except: pass
                
                for port in old_replicas:
                    if port not in new_ports:
                        url = f"http://127.0.0.1:{port}"
                        if url in hash_ring.all_nodes_ui and hash_ring.all_nodes_ui[url]['active']:
                            try: requests.post(f"{url}/delete", json={"key": key}, timeout=1.0)
                            except: pass

                stored_keys_info[key]["replicas"] = new_ports
                if "angle" not in stored_keys_info[key]:
                    stored_keys_info[key]["angle"] = hash_ring._hash_to_angle(key)
                migrated_keys += 1
                
    return migrated_keys

@api_bp.route('/status')
def status():
    return jsonify({"nodes": hash_ring.all_nodes_ui, "keys": stored_keys_info})

@api_bp.route('/sync', methods=['GET'])
def sync_data():
    global stored_keys_info
    new_keys = {}
    session = requests.Session()
    for url, info in hash_ring.all_nodes_ui.items():
        if info['active']:
            try:
                res = session.get(f"{url}/get_all", timeout=0.5).json()
                if res.get('status') == 'success':
                    port = str(res['node'])
                    for k in res.get('keys', []):
                        if k not in new_keys: 
                            new_keys[k] = {"replicas": [], "angle": hash_ring._hash_to_angle(k)}
                        if port not in new_keys[k]["replicas"]: 
                            new_keys[k]["replicas"].append(port)
            except: pass
    stored_keys_info = new_keys
    return jsonify({"status": "success"})

@api_bp.route('/add_node', methods=['POST'])
def add_node():
    hash_ring.add_node(request.json['url'])
    migrated_count = rebalance_data()
    msg = f"Server đã online."
    if migrated_count > 0: msg += f" Tự động di chuyển (Rebalance) thành công {migrated_count} Keys!"
    return jsonify({"status": "success", "message": msg})

@api_bp.route('/toggle_node', methods=['POST'])
def toggle():
    hash_ring.toggle_node(request.json['url'])
    if hash_ring.all_nodes_ui[url]['active']:
        rebalance_data()
    return jsonify({"status": "success"})

@api_bp.route('/set', methods=['POST'])
def set_data():
    data = request.json
    targets = hash_ring.get_target_nodes(data['key'], int(data.get('replicas', 1)))
    success = []
    for node in targets:
        try:
            requests.post(f"{node}/set", json=data, timeout=1.0)
            success.append(node.split(':')[-1])
        except: hash_ring.toggle_node(node, False)
        
    stored_keys_info[data['key']] = {
        "replicas": success,
        "angle": hash_ring._hash_to_angle(data['key'])
    }
    return jsonify({"status": "success", "message": f"Ghi thành công vào Port: {', '.join(success)}"})

@api_bp.route('/get')
def get_data():
    key = request.args.get('key')
    if key not in stored_keys_info: return jsonify({"status": "error", "message": "Key chưa tồn tại"})
    
    for port in stored_keys_info[key]["replicas"]:
        url = f"http://127.0.0.1:{port}"
        if url in hash_ring.all_nodes_ui and hash_ring.all_nodes_ui[url]['active']:
            try:
                res = requests.get(f"{url}/get?key={key}", timeout=1.0).json()
                if res.get('status') == 'success': 
                    return jsonify({"status": "success", "value": res['value'], "fetched_from": f"Port {port}"})
            except: hash_ring.toggle_node(url, False)
    return jsonify({"status": "error", "message": "Tất cả server chứa dữ liệu đã sập!"})