from flask import Blueprint, request, jsonify
import hashlib, bisect, requests
import time
import threading

api_bp = Blueprint('api', __name__)

class RealConsistentHashRing:
    def __init__(self, vnodes=3):
        self.vnodes = vnodes
        self.active_ring = {} 
        self.sorted_keys = [] 
        self.all_nodes_ui = {} 

    def _hash_to_angle(self, key):
        raw_hash = int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16)
        return round((raw_hash % 3600000) / 10000.0, 4)

    def add_node(self, node_url):
        if node_url not in self.all_nodes_ui:
            self.all_nodes_ui[node_url] = {"active": True, "vnodes": []}
            for i in range(self.vnodes):
                vnode_id = f"{node_url}#v{i}"
                angle = self._hash_to_angle(vnode_id)
                existing_angles = [v['angle'] for node in self.all_nodes_ui.values() for v in node['vnodes']]
                while angle in existing_angles:
                    angle = round((angle + 0.0001) % 360, 4)
                self.all_nodes_ui[node_url]['vnodes'].append({"id": vnode_id, "angle": angle})
            self._rebuild_ring()

    def toggle_node(self, node_url, force_state=None):
        if node_url in self.all_nodes_ui:
            if force_state is not None:
                self.all_nodes_ui[node_url]['active'] = force_state
            else:
                self.all_nodes_ui[node_url]['active'] = not self.all_nodes_ui[node_url]['active']
            self._rebuild_ring()

    def _rebuild_ring(self):
        self.active_ring.clear()
        self.sorted_keys.clear()
        for physical_url, info in self.all_nodes_ui.items():
            if info['active']:
                for vnode in info['vnodes']:
                    self.active_ring[vnode['angle']] = physical_url
                    self.sorted_keys.append(vnode['angle'])
        self.sorted_keys.sort()

    def get_target_nodes(self, key, replicas=1):
        if not self.sorted_keys: return []
        angle = self._hash_to_angle(key)
        idx = bisect.bisect_right(self.sorted_keys, angle)
        if idx == len(self.sorted_keys): idx = 0
        
        targets = []
        start_idx = idx
        while len(targets) < replicas and len(targets) < len(self.all_nodes_ui):
            physical_url = self.active_ring[self.sorted_keys[idx]]
            if physical_url not in targets:
                targets.append(physical_url)
            idx = (idx + 1) % len(self.sorted_keys)
            if idx == start_idx: break
        return targets

hash_ring = RealConsistentHashRing(vnodes=3)
stored_keys_info = {}

def rebalance_data():
    print("[REBALANCE] Bắt đầu quét chủ động toàn bộ cụm dữ liệu...")
    logs = []
    
    for key, info in list(stored_keys_info.items()):
        expected_count = info.get("expected_replicas", 1)
        new_targets = hash_ring.get_target_nodes(key, expected_count)
        
        current_ports = sorted(list(str(p) for p in info["replicas"]))
        new_ports = sorted(list(url.split(':')[-1] for url in new_targets))
        
        is_moved = current_ports != new_ports
        
        latest_val, latest_ts = None, -1
        for port in info["replicas"]:
            try:
                res = requests.get(f"http://127.0.0.1:{port}/get?key={key}", timeout=1.0)
                if res.status_code == 200:
                    data = res.json()['value']
                    if data['timestamp'] > latest_ts:
                        latest_ts, latest_val = data['timestamp'], data['data']
            except: pass
        
        if latest_val is None: 
            del stored_keys_info[key] 
            continue 
        
        payload = {"key": key, "value": {"data": latest_val, "timestamp": latest_ts}}
        active_replicas = []
        for target_url in new_targets:
            try:
                requests.post(f"{target_url}/set", json=payload, timeout=1.0)
                active_replicas.append(target_url.split(':')[-1])
            except: pass
            
        old_urls = [f"http://127.0.0.1:{p}" for p in info["replicas"]]
        for old_url in old_urls:
            if old_url not in new_targets:
                try: requests.post(f"{old_url}/delete", json={"key": key}, timeout=1.0)
                except: pass
                
        if key in stored_keys_info:
            stored_keys_info[key]["replicas"] = active_replicas
            
        if is_moved:
            old_str = f"[{', '.join(current_ports)}]"
            new_str = f"[{', '.join(new_ports)}]"
            logs.append(f"• Key <b>'{key}'</b>: Di chuyển từ Node {old_str} → sang chủ mới {new_str}")
            
    return logs

@api_bp.route('/add_node', methods=['POST'])
def add_node():
    url = request.json['url']
    hash_ring.add_node(url)
    return jsonify({"status": "success", "message": f"Đã thêm {url} thành công (Dữ liệu ở trạng thái Lazy)"})

@api_bp.route('/toggle_node', methods=['POST'])
def toggle():
    url = request.json['url']
    hash_ring.toggle_node(url)
    return jsonify({"status": "success"})

@api_bp.route('/status')
def status():
    return jsonify({"nodes": hash_ring.all_nodes_ui, "keys": stored_keys_info})

@api_bp.route('/set', methods=['POST'])
def set_data():
    data = request.json
    key, value, replicas = data['key'], data['value'], int(data.get('replicas', 1))
    
    timestamp = int(time.time() * 1000)
    payload = {"key": key, "value": {"data": value, "timestamp": timestamp}}

    targets = hash_ring.get_target_nodes(key, replicas)
    success = []
    for node in targets:
        try:
            requests.post(f"{node}/set", json=payload, timeout=1.0)
            success.append(node.split(':')[-1])
        except: hash_ring.toggle_node(node, False)
            
    if key not in stored_keys_info: stored_keys_info[key] = {}
    stored_keys_info[key]["replicas"] = success
    stored_keys_info[key]["expected_replicas"] = replicas
    stored_keys_info[key]["angle"] = hash_ring._hash_to_angle(key)
    
    return jsonify({"status": "success", "message": f"Ghi thành công vào Port: {', '.join(success)}"})

@api_bp.route('/get')
def get_data():
    key = request.args.get('key')
    if key not in stored_keys_info: 
        return jsonify({"status": "error", "message": "Key không tồn tại trên hệ thống!"})
    
    expected_count = stored_keys_info[key].get("expected_replicas", len(stored_keys_info[key]["replicas"]))
    current_targets = hash_ring.get_target_nodes(key, expected_count)
    
    latest_val, latest_timestamp, latest_node = None, -1, None
    responses = {}
    
    # 1. Gửi request đọc đến các Node
    for url in current_targets:
        if hash_ring.all_nodes_ui.get(url, {}).get('active'):
            try:
                res = requests.get(f"{url}/get?key={key}", timeout=1.0)
                if res.status_code == 200:
                    node_data = res.json().get('value')
                    responses[url] = node_data
                    if node_data and node_data['timestamp'] > latest_timestamp:
                        latest_timestamp, latest_val, latest_node = node_data['timestamp'], node_data['data'], url.split(':')[-1]
                else:
                    responses[url] = None
            except:
                # Node sập -> đánh dấu Offline
                hash_ring.toggle_node(url, force_state=False)
                responses[url] = None
        else:
            responses[url] = None # Node đang đánh dấu Sập -> Bỏ qua

    # 2. Kiểm tra nếu không lấy được dữ liệu từ bất kỳ Node nào
    if latest_val is None:
        if key in stored_keys_info: del stored_keys_info[key]
        return jsonify({"status": "error", "message": "Không thể lấy dữ liệu (Các node chứa dữ liệu đều đang ngoại tuyến)!"})

    # 3. Read-Repair: CHỈ SỬA KHI DỮ LIỆU THỰC SỰ LỆCH
    repair_logs = []
    active_replicas = []
    
    repair_payload = {"key": key, "value": {"data": latest_val, "timestamp": latest_timestamp}}
    
    for url, node_data in responses.items():
        port_num = url.split(':')[-1]
        
        # Chỉ repair nếu: Node đang active VÀ (dữ liệu cũ HOẶC chưa có dữ liệu)
        if hash_ring.all_nodes_ui.get(url, {}).get('active'):
            if node_data is None or node_data['timestamp'] < latest_timestamp:
                try:
                    requests.post(f"{url}/set", json=repair_payload, timeout=1.0)
                    repair_logs.append(port_num)
                    active_replicas.append(port_num)
                except:
                    pass # Node vừa sập trong lúc sửa -> bỏ qua
            else:
                active_replicas.append(port_num)
        else:
            # Nếu node sập, không repair, nhưng vẫn giữ trong danh sách replicas nếu nó là node cần có
            if url in current_targets:
                active_replicas.append(port_num)

    stored_keys_info[key]["replicas"] = list(set(active_replicas))
        
    msg = f"Đọc dữ liệu từ Node {latest_node}"
    # Chỉ thông báo sửa lỗi nếu thực sự có hành động set dữ liệu mới cho node khác
    if repair_logs:
        msg += f"<br>🛠️ <b class='text-amber-600'>[READ-REPAIR] Đã đồng bộ dữ liệu chuẩn sang Node: {', '.join(repair_logs)}</b>"
    
    return jsonify({"status": "success", "value": latest_val, "fetched_from": msg})

@api_bp.route('/rebalance', methods=['POST'])
def trigger_rebalance():
    move_logs = rebalance_data()
    if move_logs:
        return jsonify({
            "status": "success", 
            "message": "⚖️ <b>Tái cân bằng thành công! Chi tiết dịch chuyển:</b><br>" + "<br>".join(move_logs)
        })
    else:
        return jsonify({
            "status": "success", 
            "message": "✅ Toàn bộ dữ liệu hiện tại đã nằm đúng vị trí tối ưu trên dải băm VNodes, không cần di chuyển."
        })