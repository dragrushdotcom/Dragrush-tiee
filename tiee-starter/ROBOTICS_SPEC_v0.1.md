# TiEE Robotics Experiment Specification v0.1

Status: DEFINED — proposed implementation contract; robot not yet implemented.
Owner: Dragrush AI. Scope: experimental 2D warehouse simulation.

## 1. Evidence and question

The saved foundation at commit 256700a passed 49 PostgreSQL correctness tests.
The database-probe-v04 branch records 9 initial and 90 repeated synchronous
database trials, all passing their correctness checks. The repeated probe
showed no consistent TiEE throughput advantage over its controls. Those
results remain valid evidence and must not be replaced by robotics results.

HYPOTHESIS: selective processing of sensor updates can reduce computation
while preserving mapping quality, timely obstacle response and delivery success.
The experiment tests benefit over both full processing and ordinary filtering.
It makes no real-robot safety, battery, GPU, or 20x performance claim.

## 2. First deliverable and limits

Implement a Python standard-library simulator, command-line experiment runner,
JSON evidence, and a browser replay of recorded trajectories. Target the existing
2-CPU Codespace; record actual runtime and memory, with no guarantee of real-time
operation. Browser rendering is outside performance timing.

The robot is a disc of radius 0.20 m in a 12 m by 8 m warehouse, delivering one
package from a pickup waypoint to a destination. Maximum translation is 0.50 m/s.
Use a 0.10 m occupancy grid, 20 ms simulation steps and a controller at 10 Hz.
The first model is planar and kinematic; it does not model traction, actuator
dynamics, battery discharge or humanoid balance.

Use the same A* planner (8-connected, no diagonal corner cutting), obstacle
inflation by robot radius plus 0.10 m, waypoint follower and tie-breaking order
in every arm. Plan at 2 Hz using the latest processed map. Unknown cells are
traversable at twice the known-free traversal cost. Log no-path states and stop
when no path is available. Mission timeout is 120 simulated seconds.

## 3. Observation and authority boundaries

The simulator privately owns true obstacle geometry and collision detection.
The robot receives only a starting static floor plan, pose observations and
timestamped sensor readings. The true dynamic scene is evaluator-only.

Mapping sensor: 36 equally spaced range rays, 360-degree coverage, maximum
range 4 m, generated at 20 Hz. Each frame includes schema_version, event_id,
sequence, capture_time, delivery_time, pose and ranges. Validate lengths,
finite numeric values, range bounds, identities and timestamps at ingress.

SAFETY CONSTRAINT: a separate proximity channel and stop controller bypass all
filtering in every arm. Within the simulation, stop translation if an obstacle
is detected within 0.50 m ahead, or proximity readings are older than 100 ms.
The stop controller uses its own sensor observations, never true geometry.
This is an experimental simulated interlock, not a real-world safety design.

TiEE v0.1 only selects mapping updates. It cannot issue motion commands, alter
the controller, change speed limits or suppress the independent stop channel.
Report interlock interventions: it could conceal poor mapping by repeatedly
stopping the robot. A stopped robot must not appear successful merely because
it avoids collisions.

## 4. Comparison arms

R0 — full processing: enqueue every valid, nonduplicate mapping frame.
R1 — simple control: at 5 Hz select the newest available valid mapping frame;
discard superseded frames with a recorded disposition.
RT — TiEE: apply the following fixed heuristic to select mapping frames.

All arms share exact-identity deduplication, validation, mapper, planner,
controller, queue capacity, stale-frame rule, sensors and simulated resources.
Exact duplicate handling is a basic baseline capability, not a TiEE advantage.

Proposed RT scoring contract (not a calibrated probability or the book's full EV):
- Compare ranges with the last selected frame.
- N = fraction of rays differing by at least 0.10 m; N lies in [0,1].
- A = min(1, simulated time since last selection / 0.20 seconds).
- Score S = N + A - 1.
- Select the first valid frame. Subsequently ALLOW when S >= 0; otherwise REJECT.
- Decision reasons: FIRST_FRAME, NOVELTY_OR_AGE, REDUNDANT_UPDATE.

This heuristic must be named novelty-age-v1 and identified as a robotics
experiment, not silently equated with validated expected-value inference.
No learning or online parameter adaptation occurs in v0.1.

## 5. Queue, state and accounting

Each arm has one mapping worker and a FIFO capacity of 10 frames including the
in-service frame. If full, reject the newly offered frame with QUEUE_FULL; do
not silently replace queued work. Drop frames older than 250 ms before starting
mapping with STALE_FRAME. Timestamps are simulated monotonic time.

No internal DEFER state in this first experiment; queued work is ALLOW work
waiting for service. Every delivered frame has one terminal outcome: processed,
filtered, duplicate, invalid, queue_full or stale. At mission end, drain pending
mapping for at most one simulated second; mark remaining work censored and
include its processing/resource accounting separately from mission results.

Record event ID, decision, policy version, score where applicable, reason,
queue timestamps, service timestamps and output version. Evaluator labels are
joined after decisions. Observe -> score -> authorize -> execute -> verify ->
record applies here to mapping-update execution, not host privileges.

## 6. Two experiments; two clocks

A. Identical-input replay: generate a scripted trajectory and sensor recording
independent of all three arms. Feed identical bytes and timestamps to each.
Measure real process CPU and wall time for filtering, mapping, queue handling
and recording. Also report subsystem measurements. Keep identical audit work.
Compare final maps and obstacle detection against evaluator-only ground truth.

B. Closed-loop navigation: same initial worlds, scenario seeds and obstacle
motion as functions of simulated time. Observations may diverge as robot paths
diverge; do not call these identical streams. Compare task behavior under
explicit simulated mapping-service costs of 10, 50 and 100 ms per frame.

Simulated service costs are assumptions, NOT measured CPU latency. Run real
mapping code, but deliver its result at its scheduled simulated completion.
Record measured CPU/wall time separately. Do not translate simulation runtime
into robot reaction time or CPU savings. Robot performance under these resource
budgets is a modeled outcome until a wall-clock or hardware test is performed.

## 7. Scenarios and fixed evaluation set

S01 Static corridor and repetitive readings.
S02 Two available routes, with a moving obstacle blocking the shorter route.
S03 Sudden crossing obstacle; vary start times and crossing position.
S04 Mapping-sensor blackout of 0.50 seconds, with proximity channel healthy.
S05 Mapping delivery burst: hold 0.50 seconds of observations then release them.
S06 Delayed mapping frames: delay 10 percent by 300 ms; preserve capture times.
S07 Proximity-sensor blackout of 200 ms to exercise the independent stop.

Before runs, commit exact geometry, routes, spawn positions, scenario schedules,
configuration and generator hashes. Reject invalid worlds before freezing;
never remove failed evaluation seeds after results are known.

Development seeds: 1 through 10. Held-out evaluation seeds: 101 through 130.
For each scenario and service-cost setting, evaluate all arms on all 30 held-out
seeds, rotating arm execution order. Freeze policy thresholds before evaluation.
Any tuning after viewing held-out results creates a new experiment revision
and requires a new held-out set. Keep the old evidence.

## 8. Metrics and provisional acceptance gates

Always report per-arm/per-scenario results, not only aggregate averages:
- Pickup/delivery success and simulated mission duration, including timeouts.
- Collisions, minimum clearance, path length, time stopped and stop interventions.
- Map occupied-cell precision/recall and time to detect introduced obstacles.
- Mapping frame age at use, decision latency and queue waiting time.
- Input dispositions, processing calls, queue depth, censored work and errors.
- Measured total runner CPU-seconds per replay and per successful mission;
  peak process RSS; audit cost; simulator cost where separately instrumented.

Functional gate: deterministic replay, exact event accounting, no hidden-truth
access, and unit/integration checks for geometry, timestamps, stale frames,
queue limits and fail-safe stopping.

Provisional modeled-behavior gate, at every scenario/cost cell:
- At least 29 of 30 deliveries succeed in each arm for that cell to qualify
  for a success claim. Report cells where the baseline also fails.
- RT has no observed collisions and no fewer successful deliveries than either
  control. Zero observed collisions is not a safety guarantee.
- RT mission-duration p95 on jointly successful paired seeds is at most 1.05
  times each control's p95; include all failed missions separately.
- RT occupied-cell recall is within 1 percentage point of each control and
  occupied-cell precision within 2 points, using identical evaluator geometry.
- RT obstacle-detection p95 is no more than 100 simulated ms worse than either
  control. Missed detections are failures, not excluded latency samples.

Exploratory compute-benefit target on identical-input replay: at least 10 percent
lower median paired total CPU cost than BOTH controls, with correctness and
mapping-quality gates satisfied. Report all paired ratios and uncertainty.
This target is an engineering choice, not a promised result or evidence of
statistical significance. A win only against R0 establishes filtration benefit,
not an advantage over simple filtering. If RT loses, publish that outcome.

## 9. Evidence and implementation order

Suggested module layout: robotics/{world,sensors,mapper,controller,policies,
scheduler,evaluator,run}.py, robotics/scenarios/, robotics/replay.html,
tests/test_robotics_*.py. Results are grouped by experiment ID, scenario,
service cost, seed and arm, with manifest, configuration, source hashes,
raw events, trajectories, per-run metrics, failures and comparisons.

Milestone 1: freeze executable configuration and scenarios from this document.
Milestone 2: baseline robot plus independent evaluator and visual replay.
Milestone 3: R1 and RT, identical-input replay, then closed-loop trials.
Milestone 4: adversarial evaluation, complete evidence and independent rerun.
Milestone 5: higher-fidelity simulation, real sensor recordings and supervised
physical trials. Real hardware requires its own safety/control specifications.

The existing full HTTP/broker pipeline and unresolved bridge networking remain
separate tracked work; completing this simulator does not mark them complete.
The specification is committed before implementation and frozen with executable
scenario/configuration hashes before held-out evaluation.
