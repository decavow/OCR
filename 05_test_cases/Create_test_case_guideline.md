# Hướng Dẫn Viết Test Case

> Guideline viết test case dựa trên khả năng hiện tại của hệ thống (từ file tracking).

---

## 1. Nguyên Tắc

- Chỉ viết test cho những gì hệ thống **đã đáp ứng được** (DONE / PARTIAL trong tracking).
- Không viết test cho scope chưa làm hoặc thuộc phase sau.
- Cover từ **happy path → edge case → error case**.
- Tổ chức code test theo **feature/module** để dễ bổ sung khi code thay đổi.

---

## 2. Quy Trình Viết Test Case

### Bước 1: Đọc file tracking

Mở file tracking hiện tại, lọc ra các mục có status **DONE** hoặc **PARTIAL**. Mỗi mục là một nhóm test cần viết.

### Bước 2: Xác định phạm vi test cho mỗi feature

Với mỗi feature DONE/PARTIAL, liệt kê:

- **Input hợp lệ** (happy path) → Hệ thống xử lý đúng.
- **Input biên** (edge case) → Giá trị giới hạn, rỗng, tối đa.
- **Input sai** (error case) → Hệ thống từ chối đúng cách.

### Bước 3: Viết test case theo template

Mỗi test case ghi theo format:

```
Test ID:      [MODULE]-[SỐ THỨ TỰ]
Mô tả:        Hành động gì → Kỳ vọng gì
Loại:          happy / edge / error
Điều kiện:     Trạng thái trước khi test (nếu có)
Input:         Dữ liệu đầu vào
Kỳ vọng:       Kết quả mong đợi
```

### Bước 4: Sắp xếp độ khó tăng dần

Trong mỗi feature, sắp xếp test case theo thứ tự:

1. **Happy path** — Luồng chính, input chuẩn.
2. **Edge case** — Giá trị biên, trường hợp đặc biệt.
3. **Error case** — Input sai, thiếu quyền, vượt giới hạn.

---

## 3. Tổ Chức Thư Mục Test

```
05_test_cases/
├── Create_test_case_guideline.md    ← File này
│
├── [module_a]/                      ← Mỗi feature/module 1 thư mục
│   ├── test_[chức_năng_1].md        ← Test case cho chức năng con
│   ├── test_[chức_năng_2].md
│   └── ...
│
├── [module_b]/
│   ├── test_[chức_năng_1].md
│   └── ...
│
└── ...
```

**Quy tắc đặt tên:**
- Thư mục = tên module/feature (viết thường, dùng `_` nối từ).
- File = `test_` + tên chức năng cụ thể.
- Mỗi file chứa **tất cả test case** của chức năng đó (happy + edge + error).

**Tại sao tổ chức theo module?**
- Code update module nào → biết ngay cần chạy lại test nào.
- Bổ sung test case mới → thêm vào file/thư mục tương ứng, không ảnh hưởng module khác.

---

## 4. Khi Code Thay Đổi

| Tình huống | Hành động |
|------------|-----------|
| Sửa bug trong module | Chạy lại test của module đó + thêm test case cho bug vừa sửa |
| Thêm chức năng mới | Tạo file test mới trong thư mục module tương ứng |
| Thêm module mới | Tạo thư mục mới + viết test theo bước 2-4 |
| Xoá / thay đổi chức năng | Cập nhật hoặc xoá test case cũ cho khớp |

---

## 5. Ví Dụ Minh Hoạ

> Giả sử tracking ghi feature "User Auth (email/password)" = DONE.

**Thư mục:** `05_test_cases/auth/test_login.md`

```
Test ID:      AUTH-001
Mô tả:        Login với email + password đúng → thành công
Loại:          happy
Input:         email: "user@test.com", password: "Valid123!"
Kỳ vọng:       Trả về token, status 200

---

Test ID:      AUTH-002
Mô tả:        Login với password rỗng → từ chối
Loại:          edge
Input:         email: "user@test.com", password: ""
Kỳ vọng:       Trả về lỗi validation, status 422

---

Test ID:      AUTH-003
Mô tả:        Login với email không tồn tại → từ chối
Loại:          error
Input:         email: "noone@test.com", password: "abc123"
Kỳ vọng:       Trả về "invalid credentials", status 401
```
