# Trace case · C-002@11

Đối chiếu trial `E-002@11` trong hai run `E-seeded_regression-20261117-3e3c` và `E-fixed-20261117-3e3c`. Hai lượt chạy dùng cùng claim, nhãn và seed. [Report seeded_regression](../src/reports/eval_seeded_regression.json) · [Report fixed](../src/reports/eval_fixed.json)

| Trường | Kết quả |
|---|---|
| Triệu chứng | Lab 8 grader báo `status resolved != denied`. Ledger ghi 1 khoản hoàn 20.000đ, nhãn yêu cầu 0. Bước 6 báo “LogiX đã hoàn 20.000đ”. |
| Bước sai đầu tiên | **3 · `model_override` · `{"delay_days": 5}`**. Agent thay số ngày trễ đã xác minh bằng số khách tự khai trong ticket. |
| Vì sao là bước đầu tiên | Bước 1 chuyển yêu cầu tra chính sách sang investigator. Bước 2 lookup thấy đơn O-202 thuộc đúng principal và DB ghi trễ **2 ngày**. Quote 20.000đ ở bước 4 dùng giá trị đã bị sửa ở bước 3. |
| Failure mode | FM-03 trong [taxonomy](failure_taxonomy.md). |
| Đối chứng | `fixed` dùng 2 ngày từ DB. Bước 3 là `quote` với `amount_vnd: 0` và `reason: "no_entitlement"`. Kết quả là `denied`, ledger có 0 giao dịch. |
| Regression test | [`test_ticket_delay_cannot_override_db`](../src/tests/test_lab9_trace_regression.py) chạy cả hai shape. Oracle `lab8_pass` và hiệu ứng ledger phân biệt variant lỗi với bản fixed. Test vẫn bắt lỗi khi variant ghi sai tiền mà thiếu event override. |
| Chưa chắc chắn | Trace cho biết dữ kiện bị thay ở đâu. Replay này không cho biết tần suất lỗi trên LLM thật hay vì sao cách diễn đạt của người dùng có thể khiến LLM thay dữ kiện. |

```sh
# Chạy từ src/
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
python -m pytest -q -m student -o addopts= tests/test_lab9_trace_regression.py
```

Test `test_reply_reports_capped_refund` kiểm riêng FM-08 trên C-008@11. Cả hai shape ghi 20.000đ và qua grader Lab 8. Bước 5 của `seeded_regression` báo 35.000đ, nên grader mới đánh trượt. Bước 4 của `fixed` báo đúng 20.000đ.
