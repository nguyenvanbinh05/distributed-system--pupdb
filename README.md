# Dự Án PupDB - Hệ Quản Trị CSDL Phân Tán (Bản Mở Rộng)

> _Dự án này được tùy biến và phát triển mở rộng dựa trên mã nguồn gốc: [tuxmonk/pupdb](https://github.com/tuxmonk/pupdb)._

## 1. Tổng quan Dự án

**PupDB** là một cơ sở dữ liệu Key-Value (Khóa - Giá trị) mã nguồn mở, hoạt động dựa trên cơ chế lưu trữ tệp tin (file-based) cục bộ.

Thực hiện yêu cầu của bài tập môn Ứng dụng phân tán, nhóm sinh viên đã lựa chọn dự án này để tìm hiểu cấu trúc mã nguồn, triển khai cài đặt và tiến hành thực nghiệm. Điểm nhấn của dự án này là việc nhóm đã vận dụng kiến thức lý thuyết để tự lập trình và tích hợp thêm 02 tính năng phân tán hoàn toàn mới, biến một CSDL đơn lẻ thành một cụm (cluster) có khả năng tương tác và chịu lỗi.

## 2. Mục đích, Chức năng và Ứng dụng Thực tế

Dự án được ứng dụng để giải quyết các bài toán đặc thù không đòi hỏi các hệ thống quá phức tạp:

- **Mục đích:** Cung cấp giải pháp lưu trữ dữ liệu siêu nhẹ, cấu hình "Zero-setup" (không cần cài đặt server CSDL riêng biệt như MySQL hay MongoDB), giảm thiểu tài nguyên tiêu thụ.
- **Chức năng cốt lõi:**
  - `set(key, value)`: Lưu trữ hoặc cập nhật giá trị cho một khóa.
  - `get(key)`: Truy xuất dữ liệu dựa trên khóa.
  - `remove(key)`: Xóa một cặp khóa - giá trị khỏi hệ thống.
  - Lập chỉ mục (Index) tự động trên tệp JSON/Log cục bộ.
- **Ứng dụng thực tế:** Phù hợp làm bộ nhớ đệm (Cache) cho các ứng dụng web nhỏ, lưu trữ trạng thái cấu hình (State/Config storage) cho các dịch vụ Microservices, hoặc tích hợp trực tiếp vào các thiết bị IoT/Edge Computing có RAM và CPU hạn chế.

## 3. Thiết lập Môi trường và Triển khai Cụm (Cluster)

Mã nguồn dự án đã được thực nghiệm thành công và lưu trữ toàn bộ trên Github để phục vụ công tác đánh giá. Dưới đây là các bước để khởi chạy một cụm PupDB phân tán gồm 3 Node.

### 3.1. Hướng dẫn Cài đặt

1. Tải mã nguồn dự án về máy:
   ```bash
   git clone https://github.com/nguyenvanbinh05/distributed-system--pupdb.git
   cd distributed-system--pupdb
   ```
2. Kích hoạt môi trường ảo (Virtual Environment) và cài đặt thư viện:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Đối với MacOS: source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Khởi chạy các Node trên các cổng (port) khác nhau để giả lập mạng lưới:
   ```bash
   # Mở 3 terminal riêng biệt và chạy các lệnh sau:
   python node.py --port 5000 --id 1
   python node.py --port 5001 --id 2
   python node.py --port 5002 --id 3
   ```

### 3.2. Kết quả Thực nghiệm

- Mạng lưới các Node nhận diện được nhau và trao đổi thông tin thành công.
- Dữ liệu được ghi nhận chính xác vào các tệp lưu trữ riêng biệt của từng Node mà không xảy ra xung đột đọc/ghi (Read/Write conflicts).
- Cả 2 tính năng phân tán mới phát triển đều hoạt động trơn tru theo đúng thiết kế kịch bản.

---

## 4. Các Tính Năng Phân Tán Phát Triển Thêm

Để thỏa mãn tiêu chí mở rộng 02 tính năng mới liên quan đến hệ phân tán, nhóm đã tiến hành phát triển hai mô-đun quan trọng sau:

### Tính năng 1: Định tuyến Dữ liệu với Consistent Hashing (Bảng Băm Phân Tán)

- **Vấn đề giải quyết:** Nếu sử dụng hàm băm thông thường (`hash(key) % N`) để chia dữ liệu, khi số lượng Node `N` thay đổi (thêm máy hoặc sập máy), toàn bộ dữ liệu sẽ phải tính toán và di chuyển lại, gây quá tải mạng (Rebalancing Problem).
- **Cơ chế hoạt động đã lập trình:**
  - Khởi tạo một không gian băm (Hash Ring). Cả địa chỉ IP của Node và Khóa (Key) của dữ liệu đều được băm bằng thuật toán SHA-1 và đặt lên vòng tròn này.
  - Khi client gửi lệnh `set("user_1", "data")`, hệ thống băm chuỗi `"user_1"`.
  - Thuật toán sẽ quét trên vòng băm theo chiều kim đồng hồ để tìm Node lưu trữ đầu tiên có giá trị băm lớn hơn giá trị băm của key.
  - Lệnh ghi được chuyển tiếp (forward) trực tiếp đến Node đó để xử lý.
- **Lợi ích:** Hệ thống hiện tại có thể mở rộng số lượng Node (Scale-out) một cách linh hoạt. Dữ liệu được phân mảnh (Sharding) đều trên các máy, ngăn chặn tình trạng thắt cổ chai.

### Tính năng 2: Chịu lỗi với Thuật toán Bầu chọn (Bully Algorithm)

- **Vấn đề giải quyết:** Trong hệ thống cần một Node làm Điều phối viên (Leader) để quản lý metadata hoặc logs. Nếu Node này chết, toàn bộ cụm sẽ rơi vào trạng thái vô định (Single Point of Failure).
- **Cơ chế hoạt động đã lập trình:**
  - Mỗi Node tham gia mạng được gắn một định danh (ID) duy nhất.
  - Các Node định kỳ gửi tín hiệu `Heartbeat` cho Leader.
  - Khi một Node phát hiện Leader bị mất kết nối (Timeout), nó lập tức gửi thông điệp `ELECTION` tới tất cả các Node có ID lớn hơn nó.
  - Nếu không có Node ID lớn hơn nào phản hồi `OK` trong một khoảng thời gian quy định, Node đó sẽ tự thăng cấp thành Leader.
  - Node mới sẽ gửi thông điệp `COORDINATOR` đến phần còn lại của mạng lưới để cập nhật trạng thái.
- **Lợi ích:** Mang lại khả năng tự phục hồi (Self-healing). Dù các server có bị tắt đột ngột, hệ thống vẫn tự động cấu trúc lại và duy trì tính sẵn sàng cao (High Availability).

---
