# 监控 PW 测试统计收集

## 快速检查

```bash
# 检查进度
python3 extended-tests/scripts/check_pw_stats_progress.py

# 查看实时日志
tail -f extended-tests/pw_test_run.log

# 检查进程
ps aux | grep run_pw_all_with_stats | grep -v grep
```

## 当前状态

脚本正在后台运行，收集所有 PW 测试的统计信息。

## 预期输出

完成后会生成 `extended-tests/pw_test_stats.json`，包含：
- 所有测试类别的统计
- 每个测试的时间和成功率
- 自动选定的 10 个 CI quick tests

## 停止脚本

如果需要停止：
```bash
pkill -f run_pw_all_with_stats
```

## 查看结果

完成后查看选定的测试：
```bash
python3 -c "
import json
stats = json.load(open('extended-tests/pw_test_stats.json'))
print('Selected CI Tests:')
for i, test in enumerate(stats['selected_ci_tests'], 1):
    print(f'{i:2d}. {test[\"category\"]:20s} | {test[\"test_file\"]:30s} | {test[\"time\"]:6.2f}s')
"
```

