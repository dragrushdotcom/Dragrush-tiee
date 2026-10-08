# Robotics baseline v0.1a — static S01 implementation slice

Adds the robotics/ package and seven focused tests. Standard library only.
Run from tiee-starter:

```
python3 -m unittest discover -s robotics/tests -v
python3 -m robotics.run --out results/robot-baseline-001
```

Open the generated replay.html in a browser (download from Codespaces first),
or serve its output directory with Python's http.server on a private forwarded
port. The replay needs no network, packages, CDN or API keys.

The robot navigates around static shelves, visits pickup, and reaches delivery.
The baseline adds an explicit soft route cost favoring 0.75 m centre-to-wall
clearance (penalty 20 per metre of shortfall), while retaining the specified
0.30 m hard inflation. This implementation detail will be shared by all arms.
The first development run stopped indefinitely near a shelf when a shortest
path repeatedly triggered the proximity interlock. The revised planner keeps
the interlock unchanged and prefers roomier paths. Neither run is held-out
evaluation; preserve this development history with the package evidence.
An independent simulated proximity interlock checks each physics movement.
Mapping frames run through bounded FIFO service with queue-full/stale accounting.
Use --service-ms 50 or --service-ms 100 with a fresh output directory to change
the explicitly modeled mapper delay. This is not measured CPU execution latency.

Important scope: the planner currently uses the supplied static floor plan.
Range mapping updates observation sets but does not change route planning yet.
This baseline therefore cannot test the behavioral value of TiEE filtering.
Next implement sensor-driven map fusion and dynamic scenarios before R1/RT
comparisons. No TiEE speedup or real-world safety claim is supported here.

Evidence includes configuration, source/spec hashes, input sensor frames,
one terminal disposition per delivered frame, trajectories, summary metrics
and artifact checksums. Real wall/CPU measurements cover the entire simulation
(including in-memory recording), not a hardware robot or isolated mapper.
The model uses ideal pose and ranges, a kinematic disc, and static geometry.

This is a partial implementation of ROBOTICS_SPEC_v0.1.md. It has no held-out
evaluation, dynamic-map planner, R1, RT, outages, bursts or learned EV engine.
All three arms must share the eventual controller and safety-channel code.
