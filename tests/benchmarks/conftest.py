# Benchmark scripts are NOT part of the regular test suite.
# They are run manually via:
#   python tests/benchmarks/create_bench_project.py
#   python tests/benchmarks/bench_rpc_performance.py --label after --project-root PATH
#
# This conftest ensures pytest does not accidentally collect them.
collect_ignore = ["create_bench_project.py", "bench_rpc_performance.py", "profile_list_calcs.py"]
