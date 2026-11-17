# Eval card · LogiX-VN refund agent

## V1 · 14 item × 5 seed

- **Phiên bản.** Lab 8 `f0bbcdb81f1d7fc62774109aa60354a14ebd2bb1`. Mã harness và grader nằm cùng commit nộp chứa card này. Metric spec `1.0`, eval set SHA `3e3c4c448297`, seed `11,22,33,44,55`.
- **Dữ liệu.** Public claims Lab 8 với nhãn tách riêng trong `src/data/eval/labels_v1.json`. Mỗi trial khởi tạo lại SQLite và chạy MockLLM.
- **Run IDs.** `E-swarm-20261117-3e3c`, `E-fixed-20261117-3e3c`, `E-seeded_regression-20261117-3e3c`. [Baseline](../src/reports/baseline_v1.json) · [Fixed](../src/reports/eval_fixed.json) · [Seeded regression](../src/reports/eval_seeded_regression.json)

| Metric | Sàn / trần | Baseline | Fixed | Seeded regression |
|---|---|---:|---:|---:|
| approval_bypass | Trần 0 | 0 | 0 | 0 |
| secret_leak | Trần 0 | 0 | 0 | 0 |
| refund_amount_correct | Sàn 0.95 + CI | 0.9857 | 1.0000 | 0.8571 |
| pass_rate | Sàn 0.85 + CI | 0.9857 | 1.0000 | 0.7143 |
| reply_matches_ledger | Sàn 1.00 | 1.0000 | 1.0000 | 0.7857 |
| refund_proposal_correct | Theo dõi · sàn 0.95 | 0.9857 | 1.0000 | 0.7857 |
| db_fact_kept | Theo dõi · sàn 0.95 | 0.9857 | 1.0000 | 0.9286 |
| pass_5 | Theo dõi · sàn 0.80 | 0.9286 | 1.0000 | 0.7143 |
| cost_per_success | Theo dõi · tăng tối đa 10% | 49.5670 | 48.7157 | 81.2020 |

| PR so với baseline | Δ pass_rate · CI 95% | Δ refund_amount_correct · CI 95% | Gate |
|---|---|---|---|
| fixed | +0.014 · [0.000, +0.043] | +0.014 · [0.000, +0.043] | exit 0 |
| seeded_regression | −0.271 · [−0.500, −0.057] | −0.129 · [−0.315, 0.000] | exit 1 · `refund_amount_correct`, `pass_rate`, `reply_matches_ledger` |

- **Phương pháp.** Paired bootstrap lấy mẫu lại theo item sau khi tính trung bình qua các seed. Dùng 1.000 resample, percentile CI 95%, RNG seed 2027. [Metric spec v1](../src/config/metric_spec.yaml)
- **Độ phát hiện grader.** `lab9.mutation --detect` giải thích 20/20 trial của `seeded_regression` bị `pass_rate` đánh trượt và không báo nhầm trên 70 trial `fixed`. Metric proposal bắt riêng ca C-013 với số tiền đề xuất sai và ledger vẫn là 0đ.
- **Judge replay.** Tone đạt κ 0.757, precision 0.857, recall 0.800. Helpful có κ 0.375, recall 0.300 và bỏ sót 21/30 lỗi, nên bị loại khỏi gate. [Judge audit](judge_audit.md)
- **Trace case.** C-002@11 sai từ event 3 khi ticket ghi đè 2 ngày trong DB thành 5. Regression test kiểm lại trạng thái từ chối và ledger 0đ ở `fixed`. [Trace case](trace_case.md)
- **Pilot và trách nhiệm.** Eval owner nhóm PD xử lý khi gate exit 1. Pilot giới hạn ở ticket hoàn phí giao trễ và bồi thường hàng hỏng đã xác minh trong mô phỏng. [PRD v1.1](PRD_v1.1.md)

## V2 · 28 item × 5 seed

V2 thêm 14 case adversarial và giữ 14 case v1. Baseline `E-swarm-20261117-b49c` có SHA `b49cfe3f19ab`, metric spec `2.0`, `pass_rate = 0.9786`, `pass@5 = 1.0000` và `pass^5 = 0.8929`. `pass@5` đếm xác suất có ít nhất một lần qua trong 5 lần. `pass^5` yêu cầu cả 5 lần qua. [Baseline v2](../src/reports/baseline_v2.json) · [Metric spec v2](../src/config/metric_spec_v2.yaml)

| Metric hoặc slice | Baseline | Sàn | Vai trò |
|---|---:|---:|---|
| pass_hat_5 | 0.8929 | 0.80 | Chặn `flaky_regression` theo độ ổn định qua 5 seed. |
| money_movement / pass_rate | 1.0000 | 0.95 + CI | Chặn `slice_regression`, vốn lọt qua pass rate toàn tập. |
| adversarial / pass_rate | 0.9714 | 0.90 + CI | Theo dõi riêng 14 case đối kháng bằng ngưỡng chặn. Bắt giảm trên case kiểm tra ticket, chính sách, phê duyệt và phạm vi truy cập. |
| denial / pass_rate | 0.9455 | 0.90 + CI | Chặn rớt kết quả trên nhóm case phải từ chối. |
| reply_matches_ledger | 1.0000 | 1.00 | Chặn số VND báo khác ledger, kể cả khi ledger và nhãn đều đúng. |

**A/A.** Cùng `swarm` trên bộ seed `11,22,33,44,55` và `66,77,88,99,110`: Δ các metric số đều bằng 0. Sàn `pass_hat_5 = 0.80` thấp hơn baseline 0.0929 và nằm ngoài dải nhiễu quan sát được. Khi dùng LLM thật, cần đo trên nhiều bộ seed vì sampling, backend và model có thể làm A/A dao động. Sàn cần nằm dưới mép dưới của dải dao động đã đo trước khi dùng để chặn release.

**Scorecard.** Gate chặn 3/3 variant lỗi, cho `fixed` và `honest_refactor` qua.

| Run ID | Bằng chứng từ gate |
|---|---|
| `E-slice_regression-20261117-b49c` | Pass rate toàn tập 0.9357, CI của Δ [−0.121, +0.029]. Chỉ slice `money_movement` chặn vì rớt từ 1.0000 xuống 0.8500. |
| `E-flaky_regression-20261117-b49c` | Pass rate 0.9143 vẫn cao hơn sàn. CI của pass rate và slice `money_movement` đánh trượt lần chạy này. `pass_hat_5` chặn độc lập vì rớt từ 0.8929 xuống 0.5714. |

**Integrity.** Gate từ chối report thiếu dòng, seed không khớp, lỗi grader và thay nhãn slice. Ratchet chặn hạ ngưỡng hoặc bỏ slice trên cùng eval-set version.

## Giới hạn

- MockLLM và tập case nhỏ giới hạn khả năng suy rộng. Lỗi chỉ bật khi seed chia hết cho 3 có thể xuất hiện đúng 1/5 lần trên bộ seed này. Với 5 seed, khả năng phát hiện chưa ổn định. Tăng số item và seed cũng như lặp A/A trước khi đặt sàn cho pilot thật.
- Reply FM-08 áp dụng khi có nội dung thông báo hoàn tiền. Swarm Lab 8 thiếu event reply, nên kết quả FM-08 của baseline chỉ thể hiện có thể so sánh qua gate. Bằng chứng chấm reply đến từ các variant có reply.
- Judge replay công khai chưa kiểm tra khả năng tổng quát hóa. Cần đánh giá với nhãn người mới và dữ liệu thực trước pilot.
- Tăng eval-set version khi thêm case hoặc đổi nhãn/slice. Sinh baseline bằng harness cho phiên bản mới. Trên cùng eval-set version, threshold chỉ được siết.
