# ADR 0003: Performance Observations Are Non-authoritative

- Status: Accepted
- Date: 2026-08-18
- Scope: PERF-OBS-01

MRMD/PREP performance observations are optional, bounded, run-scoped operational data emitted only by the new Runtime orchestration. They never enter requests, semantic hashes, Run IDs, traces, results, evidence, repositories, cache keys, or analysis. Clock, counter, recorder, overflow, or snapshot failure cannot change or mask authoritative control flow or output; instrumentation code remains covered by normal build-artifact identity.

V1 uses one private stdlib-only Runtime aggregate recorder with a fixed operation/outcome keyspace. It adds no shared cross-package telemetry interface, logging configuration, exporter, SDK, registry, callback graph, I/O, lock, thread, or worker. Existing frozen operations are not given observer parameters. Other package owners may define later local observation plans only when a concrete implementation seam is touched; PERF-OBS-01 does not predefine their taxonomy.
