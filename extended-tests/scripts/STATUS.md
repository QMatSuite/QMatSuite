# PW 测试统计收集状态

## ✅ 脚本已启动

统计收集脚本正在后台运行，收集所有 PW 测试的统计信息。

## 运行信息

- **命令**: `python3 extended-tests/scripts/run_pw_all_with_stats.py --nprocs 4 --timeout 300`
- **进程**: 后台运行
- **日志文件**: `extended-tests/pw_test_run.log`
- **输出文件**: `extended-tests/pw_test_stats.json` (完成后生成)

## 检查进度

```bash
# 查看进度和统计
python3 extended-tests/scripts/check_pw_stats_progress.py

# 查看实时日志
tail -f extended-tests/pw_test_run.log

# 检查进程状态
ps aux | grep run_pw_all_with_stats
```

## 预期时间

- **总类别数**: ~22 个 PW 测试类别
- **每个测试**: 平均 15-30 秒（使用 NPROCS=4）
- **总时间**: 约 1-2 小时（取决于测试数量和系统性能）

## 测试结果

脚本会：
1. ✅ 运行所有 PW 测试类别
2. ✅ 收集每个测试的时间和成功率
3. ✅ 自动选择 10 个最短、最有代表性的测试
4. ✅ 生成详细的统计报告

## 完成后

统计文件生成后：
- CI quick tests 会自动加载选定的 10 个测试
- 可以查看详细的统计报告
- 可以分析测试性能和成功率

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

