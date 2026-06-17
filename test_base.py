from pupdb.core import PupDB

# Khởi tạo DB, dữ liệu sẽ lưu vào file db.json
db = PupDB('db.json')

# Thử Ghi và Đọc
db.set('hoc_phan', 'Ung dung phan tan')
print("Dữ liệu vừa lưu:", db.get('hoc_phan'))