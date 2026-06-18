# Dự Án PupDB - Hệ Quản Trị Cơ Sở Dữ Liệu Phân Tán

> _Dự án được nghiên cứu, tái cấu trúc và phát triển mở rộng dựa trên lõi cơ sở dữ liệu mã nguồn mở [PupDB: tuxmonk/pupdb](https://github.com/tuxmonk/pupdb)._

---

## 1. Tổng quan Dự án

**PupDB** nguyên bản là một hệ quản trị cơ sở dữ liệu siêu nhẹ vận hành theo mô hình Khóa - Giá trị (Key-Value), duy trì bảng băm trên RAM và lưu trữ trực tiếp xuống tệp tin định dạng JSON. Tuy nhiên, kiến trúc gốc mang nhược điểm chí mạng là **điểm lỗi duy nhất (Single Point of Failure)** và **không có khả năng mở rộng ngang (Scale-out)**.

Nhận thức được các giới hạn này, nhóm đã ứng dụng kiến thức chuyên sâu về Hệ thống phân tán để thiết kế lại toàn bộ kiến trúc, bọc thêm các lớp giao tiếp mạng qua API và nâng cấp PupDB đơn lẻ thành một **Cụm cơ sở dữ liệu phân tán (Distributed Database Cluster)** có khả năng định tuyến thông minh, sao chép dữ liệu, tự phục hồi và chịu lỗi cao.

---

## 2. Kiến trúc Hệ thống Phân tầng (Two-Tier Architecture)

Hệ thống được thiết kế phân tách thành hai tầng logic độc lập nhằm tối ưu hóa hiệu suất và dễ dàng quản lý:

- **Tầng định tuyến trung tâm (Router):** Đóng vai trò là cơ quan điều phối luồng thông tin và tiếp nhận yêu cầu từ khách hàng. Bộ định tuyến hoàn toàn không lưu trữ dữ liệu nghiệp vụ, chỉ duy trì bản đồ cấu hình mạng trên RAM và chạy các giải thuật để chuyển tiếp chính xác yêu cầu truy vấn đến đúng nút mạng lưu trữ.
- **Tầng nút mạng lưu trữ (Storage Nodes):** Cấu thành từ các tiến trình máy chủ hoạt động hoàn toàn độc lập, không chia sẻ trạng thái chung (Shared-nothing). Mỗi nút mạng tiếp nhận lệnh từ bộ định tuyến thông qua giao thức HTTP (GET/POST/DELETE) và thao tác trực tiếp trên tệp dữ liệu JSON vật lý của chính nó.

---

## 3. Các Tính Năng Phân Tán Cốt Lõi

### 3.1. Định tuyến thông minh với Băm nhất quán & Nút mạng ảo

Thay vì sử dụng phép chia lấy dư truyền thống dễ gây nghẽn mạng khi thay đổi cấu trúc, hệ thống áp dụng thuật toán **Băm nhất quán (Consistent Hashing)**:

- Hàm băm MD5 ánh xạ cả IP của nút mạng và khóa dữ liệu lên một vòng tròn tọa độ logic ($0^{\circ}$ đến $360^{\circ}$).
- Dữ liệu tự động được định tuyến theo chiều kim đồng hồ đến nút mạng gần nhất.
- **Nút mạng ảo (Virtual Nodes):** Mỗi máy chủ vật lý được nhân bản thành nhiều thực thể ảo đan xen trên vòng băm, giúp "băm mịn" không gian lưu trữ, loại bỏ hoàn toàn hiện tượng lệch tải cục bộ và san sẻ tải trọng đồng đều.

### 3.2. Tính chịu lỗi, Tự phục hồi và Xóa mềm

- **Sao chép dữ liệu (Replication):** Dữ liệu được ghi đồng thời xuống nút bản chính (Primary) và các nút bản sao (Replica) kế tiếp trên vòng băm để dự phòng rủi ro phần cứng.
- **Tự chữa lành (Read-Repair):** Áp dụng nhãn thời gian (Timestamp) cho mọi bản ghi. Khi có truy vấn đọc, hệ thống đối chiếu và trả về phiên bản mới nhất, đồng thời tự động ghi đè bản mới nhất lên các nút đang chứa dữ liệu lỗi thời.
- **Xóa mềm với Cờ báo tử (Tombstone):** Lệnh xóa không xóa vật lý ngay lập tức mà thay thế bằng cờ `__DELETED__`. Cơ chế này ngăn chặn tuyệt đối tình trạng tàn dư dữ liệu cũ (bóng ma dữ liệu) bị phục hồi ngoài ý muốn khi một nút ngoại tuyến khởi động lại.
- **Tái cân bằng chủ động (Proactive Rebalancing):** Tự động đối chiếu và chỉ dịch chuyển phần dữ liệu chênh lệch khi có máy chủ mới tham gia mạng lưới, giúp tiết kiệm tối đa băng thông.

---

## 4. Hướng dẫn Cài đặt và Vận hành

Hệ thống được phát triển trên nền tảng Python, đảm bảo khả năng chạy đa nền tảng (Windows, macOS, Linux).

### 4.1. Yêu cầu hệ thống

- Python 3.8 trở lên.
- Các thư viện phụ thuộc: `Flask`, `requests`, `pupdb`.

Cài đặt thư viện bằng lệnh:

    pip install Flask requests pupdb

### 4.2. Khởi động Cụm Phân tán (Mô phỏng máy chủ cục bộ)

**Bước 1: Khởi động các Nút lưu trữ vật lý**
Mở các cửa sổ Terminal/Command Prompt độc lập và chạy mã nguồn `node.py` kèm tham số cổng mạng:

    # Terminal 1 - Khởi chạy Node 1
    python node.py 5001

    # Terminal 2 - Khởi chạy Node 2
    python node.py 5002

    # Terminal 3 - Khởi chạy Node 3
    python node.py 5003

_(Hệ thống sẽ tự tạo các tệp `db_node_5001.json`, v.v. tại thư mục hiện hành)._

**Bước 2: Khởi động Bộ định tuyến trung tâm**
Mở một cửa sổ Terminal mới và chạy tệp thực thi chính:

    # Terminal 4 - Khởi chạy Router & Web UI
    python app.py

Truy cập Giao diện quản trị Web tại địa chỉ mặc định: `http://127.0.0.1:8000`

---

## 5. Kịch bản Thực nghiệm (Demo)

1. **Thêm nút mạng:** Trên giao diện Web, nhập lần lượt các cổng `5001`, `5002`, `5003` để đưa máy chủ vào vòng băm.
2. **Ghi và phân bổ dữ liệu:** Thực hiện lưu một Key-Value. Dữ liệu sẽ tự động được định tuyến và sao chép xuống 2 nút mạng lân cận trên vòng tọa độ.
3. **Thử nghiệm chịu lỗi:** Tắt đột ngột Terminal của Node đang giữ bản chính. Thực hiện lệnh đọc lại Key đó. Giao diện sẽ cảnh báo Node ngoại tuyến nhưng dữ liệu vẫn được truy xuất thành công từ Node bản sao.
4. **Cân bằng tải:** Bật thêm Terminal chạy `node.py 5004`, thêm vào mạng lưới và nhấn "Cân bằng tải". Quan sát nhật ký (Log) hệ thống tự động hoán chuyển vị trí dữ liệu.

---

## 6. Định hướng phát triển tương lai

Nhằm tiệm cận hơn với các hệ quản trị dữ liệu lớn như Cassandra hay DynamoDB, hệ thống có thể tiếp tục mở rộng:

- Triển khai cơ chế **Anti-Entropy** tự động để các nút định kỳ tự trao đổi và đồng bộ dữ liệu ngầm.
- Xây dựng **Giao thức Gossip** để phân tán việc quản lý trạng thái máy chủ, giảm tải cho bộ định tuyến trung tâm.
- Ứng dụng **Đồng hồ Vector (Vector Clock)** thay cho nhãn thời gian đơn thuần để kiểm soát xung đột dữ liệu đa phiên bản chính xác hơn.

---
