# Judge audit

Chạy từ `src/` với `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5` và lặp lại cho `judge_helpful_public.csv`. Lớp dương là FAIL. Sàn là κ ≥ 0.6, precision ≥ 0.8, recall ≥ 0.7.

| Tiêu chí | n | TP / FP / FN / TN | κ | Precision | Recall | Fail quan sát → hiệu chỉnh | Quyết định |
|---|---:|---|---:|---:|---:|---|---|
| tone_ok | 100 | 24 / 4 / 6 / 66 | 0.757 | 0.857 | 0.800 | 28% → 30% | Đạt cả ba sàn, dùng cho đánh giá giọng điệu |
| helpful | 100 | 9 / 0 / 21 / 70 | 0.375 | 1.000 | 0.300 | 9% → 30% | Loại khỏi gate |

## Audit bất đồng

| Case | Judge | Người | Phân xử | Sửa rubric |
|---|---|---|---|---|
| H-008 | PASS | FAIL | Người đúng. Cách xưng “em” cùng “nha” suồng sã so với quy chuẩn hỗ trợ. | Chấm mức độ trang trọng theo cả cặp xưng hô và từ kết câu. |
| H-017 | PASS | FAIL | Người đúng theo bối cảnh khách lớn tuổi trong ghi chú. | Thêm ví dụ trong đó “Dạ” đi cùng “bạn ơi … nha” vẫn trượt. |
| H-029 | PASS | FAIL | Người đúng. “Không cần nhắn thêm” gạt khách sang một bên. | Chấm cả nội dung hướng dẫn. Yêu cầu nêu bước tiếp theo bằng giọng trung tính. |
| H-042 | FAIL | PASS | Người đúng. Tin nhắn xác nhận số tiền và thời gian nhận bằng giọng lịch sự. | Chỉ yêu cầu lời xin lỗi khi bối cảnh có sự cố chưa được ghi nhận. Cho qua xác nhận ngắn và lịch sự. |
| H-051 | FAIL | PASS | Người đúng. “Refund” nằm trong từ vựng CS LogiX cho phép. | Liệt kê từ vay mượn được phép. Chấm độ dễ hiểu của cả câu. |
| HL-015 | PASS | FAIL | Người đúng. Reply báo 55.000đ, ledger ghi 40.000đ. | Bắt buộc đối chiếu số tiền với ledger bằng code trước khi chấm hữu ích. |
| HL-020 | PASS | FAIL | Người đúng. Reply báo 90.000đ, ledger ghi 120.000đ. | Đưa cả hai chiều báo thừa và báo thiếu vào ví dụ FAIL. |
| HL-047 | PASS | FAIL | Người đúng theo quy chuẩn xưng hô. “Xử lý rồi” cũng thiếu kết quả cụ thể. | Tách yêu cầu về kết quả xử lý khỏi tiêu chí giọng điệu. |

Judge helpful bỏ sót 21 trong 30 lỗi do người gắn nhãn. Precision 1.000 chỉ phản ánh 9 lỗi judge đã báo. Hiệu chỉnh Rogan–Gladen ước lượng tỷ lệ lỗi chung trên tập replay và không sửa được 21 quyết định ở cấp từng case.

Các kết quả trên dùng CSV công khai với nhãn có sẵn. Cần tập held-out có nhãn người mới trước khi áp dụng judge cho pilot. Tiền và phê duyệt được chấm bằng code.
