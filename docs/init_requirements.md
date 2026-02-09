# Initial Requirements

## 1. Business Requirements
- Khi upload lên, mặc định sẽ xoá trong 24 giờ
- Khi upload tài liệu người dùng có thể chọn thời gian expired date, còn không mặc định sẽ là default 24h
- Người dùng có thể chọn lựa các phương pháp ocr (text only, table, code,...), mỗi phương thức sẽ tương ứng với 1 service xử lý riêng -> ngươi dùng chịu trách nhiệm hoàn toàn về mặt output, backend sẽ không tự auto detect
- Người dùng có thể lựa chọn mức độ bảo mật của tài liệu -> càng cao tương ứng với hạ tầng càng đắt -> tốn nhiều chi phí hơn
- Người dùng có thể cancel nếu request chưa được xử lý 
- Người dùng có thể upload tài liệu theo batch, chọn loại service để xử lý (thời gian nhanh tương ứng với tốn nhiều tiền hơn)
- Trả phí theo pay as you go
- Người dùng sẽ nhận được thông báo (noti) là data đã được xử lý xong. Màn hình kết quả là một giao diện khác
- NGười dùng có thể quản lý được lịch sử xử lý của mình

## 2. Technical Requirements
- Các service sẽ xử lý độc lập với nhau, chỉ gọi qua nhau bằng API
    - cloudfare chỉ sử dụng để lưu trữ và nhận thông tin từ đầu client, không sử dụng để xử lý
    - GCP phục vụ cho luồng xử lý logic của hệ thống, điều hướng dữ liệu, lưu log và quản trị tập trung (admin)
    - Vast.AI, selfhosted,  phục vụ cho việc xử lý OCR

*Ma trận phân lớp service OCR*
```
Chiều ngang: HẠ TẦNG (tier)
                 ─────────────────────────────────────▶
                  Tier 0     Tier 1     Tier 2    Tier 3    Tier 4
              ┌──────────┬──────────┬──────────┬─────────┬──────────┐
 Chiều   ocr_ │          │          │          │         │          │
 dọc:    simple│  Local   │ Vast.ai  │  RunPod  │ RunPod  │   VIP    │
              ├──────────┼──────────┼──────────┼─────────┼──────────┤
 NGHIỆP  ocr_ │          │          │          │         │          │
 VỤ      table│  Local   │ Vast.ai  │  RunPod  │ RunPod  │   VIP    │
              ├──────────┼──────────┼──────────┼─────────┼──────────┤
 (method) ocr_│          │          │          │         │          │
         code │  Local   │ Vast.ai  │  RunPod  │ RunPod  │   VIP    │
              └──────────┴──────────┴──────────┴─────────┴──────────┘
                                │                    │
                                │                    │
                          Cùng kết quả          Cùng kết quả
                          Khác bảo mật          Khác bảo mật
                          Khác giá              Khác giá
```                          

- Cho phép người dùng lựa chọn phương thức xử lý bằng cách chọn config đề xuất
- Các hệ thống OCR selfhosted sẽ rẻ hơn so với chạy vast.ai và tăng giá dần nếu muốn sử dụng hạ tầng đắt hơn
- Với các hệ thống OCR có thể scale theo hướng horizontal dễ dàng
- Mỗi worker sẽ có thời gian estimate để xử lý, nếu không xử lý trong đúng thời gian sẽ được đánh dấu task đó là failed và chuyển sang deadqueue
- Không có retry trong 1 worker -> fail 1 step là fail cả job


