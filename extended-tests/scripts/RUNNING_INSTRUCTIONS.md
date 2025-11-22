# 运行 PW 测试统计收集

## 当前状态

统计收集脚本已在后台启动。

## 检查进度

```bash
# 查看进度
python3 extended-tests/scripts/check_pw_stats_progress.py

# 查看实时日志
tail -f extended-tests/pw_test_run.log

# 检查进程
ps aux | grep run_pw_all_with_stats
```

## 预期时间

- 所有 PW 测试类别：约 25-30 个类别
- 每个测试：平均 15-30 秒（使用 NPROCS=4）
- 总时间：约 1-2 小时（取决于测试数量和系统性能）

## 输出文件

- `extended-tests/pw_test_stats.json` - 完整的统计信息
- `extended-tests/pw_test_run.log` - 运行日志

## 完成后

统计文件生成后，CI quick tests 会自动加载选定的 10 个测试。

查看结果：
```bash
python3 extended-tests/scripts/check_pw_stats_progress.py
```

查看选定的测试：
```bash
python3 -c "
import json
from pathlib import Path
stats = json.load(open('extended-tests/pw_test_stats.json'))
print('Selected CI Tests:')
for i, test in enumerate(stats['selected_ci_tests'], 1):
    print(f'{i:2d}. {test[\"category\"]:20s} | {test[\"test_file\"]:30s} | {test[\"time\"]:6.2f}s')
"
```

