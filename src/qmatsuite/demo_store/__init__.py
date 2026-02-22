"""
Demo store: two-layer demo system (corpus -> translator -> demo snapshots).

Layer A: Corpus at tests/inputformat/samples/<engine>/
Layer B: Demo snapshots at src/qmatsuite/resources/demo_projects/<demo_slug>.yml

The translator is the single writer that converts eligible corpus cases
to demo project snapshots.
"""
