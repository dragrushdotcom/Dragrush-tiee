# Baseline development verification

Local checks: seven focused tests passed; a complete default mission delivered
in 39.9 simulated seconds, zero collisions, 798/798 processed frames, minimum
clearance approximately 0.549 m. A repeat produced an identical trajectory.
At modeled 100 ms mapping service, 401 frames processed and 397 expired; all
798 were accounted for. The route remained identical because this slice uses
the known static floor plan, not sensor-driven navigation.

Included development evidence:
- robot-local-001: failed shortest-path route; interlock stopped near a shelf.
- robot-local-002: preferred-clearance route; successful default mission.
- robot-local-003: current runner with modeled 100 ms mapper; successful mission.

These are development runs, not held-out evaluation. The first failure is
preserved. Its planner source predates the preferred-clearance addition and is
not separately bundled; its manifest records that earlier source's hashes.
All source/configuration changes are documented in ROBOTICS_BASELINE_README.md.

Replay JavaScript syntax checked using Node. A local graphical browser executable
was unavailable, so interactive playback/rendering must be checked by opening
the generated replay in the user's browser. Simulation output itself was run.

No real-world safety, latency, battery, GPU or TiEE benefit claim is established.
