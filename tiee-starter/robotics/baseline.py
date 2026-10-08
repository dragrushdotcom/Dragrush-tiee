"""S01 static warehouse baseline. Distances metres, simulated times milliseconds."""
from collections import Counter, deque
import hashlib
import heapq
import json
import math

CONFIG = {
    'experiment': 'robotics-s01-baseline-v1', 'scenario': 'S01', 'arm': 'R0',
    'width_m': 12, 'height_m': 8, 'robot_radius_m': .20,
    'clearance_margin_m': .10, 'grid_m': .10, 'max_speed_m_s': .50,
    'physics_step_ms': 20, 'controller_period_ms': 100,
    'planner_period_ms': 500, 'mapping_sensor_period_ms': 50,
    'proximity_sensor_period_ms': 20, 'proximity_stale_ms': 100,
    'proximity_stop_m': .50, 'mapping_rays': 36, 'range_m': 4,
    'queue_capacity_including_service': 10, 'stale_mapping_ms': 250,
    'timeout_ms': 120000, 'drain_ms': 1000,
    'start': [1.0, 1.0], 'pickup': [1.5, 1.5], 'destination': [10.5, 6.5],
    'planner_preferred_clearance_m': .75, 'planner_clearance_penalty_per_m': 20,
    'walls': [[3.0, .5, 4.0, 5.5], [7.0, 2.5, 8.0, 7.5]],
}


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def clearance(x, y, walls, width=12, height=8):
    """Evaluator geometry: nearest distance from centre to a wall or boundary."""
    distance = min(x, y, width-x, height-y)
    for x0, y0, x1, y1 in walls:
        dx, dy = max(x0-x, 0, x-x1), max(y0-y, 0, y-y1)
        distance = min(distance, math.hypot(dx, dy))
    return distance


def ray_box(x, y, dx, dy, box):
    near, far = -float('inf'), float('inf')
    for position, direction, low, high in ((x, dx, box[0], box[2]), (y, dy, box[1], box[3])):
        if abs(direction) < 1e-12:
            if position < low or position > high:
                return float('inf')
        else:
            a, b = (low-position)/direction, (high-position)/direction
            near, far = max(near, min(a,b)), min(far, max(a,b))
    if far < max(0, near):
        return float('inf')
    return max(0, near)


def sensor_range(x, y, angle, config):
    """Sensor simulator alone reads the true geometry."""
    dx, dy = math.cos(angle), math.sin(angle)
    distances = [config['range_m']]
    if dx > 1e-12:
        distances.append((config['width_m']-x)/dx)
    elif dx < -1e-12:
        distances.append(-x/dx)
    if dy > 1e-12:
        distances.append((config['height_m']-y)/dy)
    elif dy < -1e-12:
        distances.append(-y/dy)
    distances.extend(ray_box(x,y,dx,dy,box) for box in config['walls'])
    return max(0, min(distances))


def mapping_frame(sequence, t, pose, config):
    ranges = [sensor_range(pose[0],pose[1],i*math.tau/36,config) for i in range(36)]
    content = {'schema_version':'robot-range-v1', 'sequence':sequence,
               'capture_time_ms':t, 'delivery_time_ms':t,
               'pose':list(pose), 'ranges':ranges}
    return {'event_id':hashlib.sha256(canonical(content)).hexdigest(), **content}


class Mapper:
    """Uses the supplied static floor plan and delivered frames, not world state."""
    def __init__(self, config):
        self.resolution = config['grid_m']
        self.width = round(config['width_m']/self.resolution)
        self.height = round(config['height_m']/self.resolution)
        self.radius = config['robot_radius_m']+config['clearance_margin_m']
        self.blocked = set()
        self.travel_cost = {}
        # The experiment explicitly supplies the static floor plan to all arms.
        for iy in range(self.height):
            for ix in range(self.width):
                x,y = self.centre((ix,iy))
                distance = clearance(x,y,config['walls'],config['width_m'],config['height_m'])
                self.travel_cost[ix,iy] = 1 + max(0,config['planner_preferred_clearance_m']-distance)*config['planner_clearance_penalty_per_m']
                if distance <= self.radius:
                    self.blocked.add((ix,iy))
        self.observed = set()
        self.hits = set()
        self.version = 0
        self.last_capture = None

    def cell(self, p):
        return (int(p[0]/self.resolution), int(p[1]/self.resolution))

    def centre(self, cell):
        return ((cell[0]+.5)*self.resolution, (cell[1]+.5)*self.resolution)

    def apply(self, frame):
        x,y = frame['pose'][:2]
        for i, distance in enumerate(frame['ranges']):
            dx,dy = math.cos(i*math.tau/36),math.sin(i*math.tau/36)
            for step in range(int(distance/self.resolution)+1):
                cell = self.cell((x+dx*step*self.resolution,y+dy*step*self.resolution))
                if 0 <= cell[0] < self.width and 0 <= cell[1] < self.height:
                    self.observed.add(cell)
            if distance < 4-1e-9:
                self.hits.add(self.cell((x+dx*distance,y+dy*distance)))
        self.version += 1
        self.last_capture = frame['capture_time_ms']

    def path(self, start, target):
        """Static floor-plan route. Dynamic map fusion is deliberately not implemented."""
        origin, goal = self.cell(start), self.cell(target)
        if origin in self.blocked or goal in self.blocked:
            return []
        def h(c):
            return math.hypot(c[0]-goal[0], c[1]-goal[1])
        pending = [(h(origin),0,origin)]
        costs, parents = {origin:0}, {}
        while pending:
            _,cost,current = heapq.heappop(pending)
            if cost > costs[current]+1e-12:
                continue
            if current == goal:
                route = [current]
                while route[-1] != origin:
                    route.append(parents[route[-1]])
                return [self.centre(c) for c in reversed(route)]
            for dx,dy in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
                nxt = current[0]+dx,current[1]+dy
                if not 0 <= nxt[0] < self.width or not 0 <= nxt[1] < self.height or nxt in self.blocked:
                    continue
                if dx and dy and ((current[0]+dx,current[1]) in self.blocked or
                                  (current[0],current[1]+dy) in self.blocked):
                    continue
                new_cost = cost+math.hypot(dx,dy)*self.travel_cost.get(nxt,1)
                if new_cost < costs.get(nxt,float('inf')):
                    costs[nxt],parents[nxt] = new_cost,current
                    heapq.heappush(pending,(new_cost+h(nxt),new_cost,nxt))
        return []


def stop_required(proximity, now):
    return proximity is None or now-proximity['capture_time_ms'] > 100 or min(proximity['ranges']) <= .50


class Worker:
    def __init__(self, mapper, service_ms):
        self.mapper,self.service_ms = mapper,service_ms
        self.queue,self.active = deque(),None
        self.events,self.seen = [],set()
        self.max_depth = 0

    def terminal(self, frame, outcome, now, **extra):
        self.events.append({'event_id':frame.get('event_id'), 'sequence':frame.get('sequence'),
                            'capture_time_ms':frame.get('capture_time_ms'),
                            'delivery_time_ms':frame.get('delivery_time_ms'),
                            'finished_ms':now, 'outcome':outcome, 'policy':'R0-full-v1', **extra})

    def offer(self, frame, now):
        valid = (frame.get('schema_version')=='robot-range-v1' and
                 isinstance(frame.get('event_id'),str) and len(frame['event_id'])==64 and
                 type(frame.get('sequence')) is int and frame['sequence']>=0 and
                 type(frame.get('capture_time_ms')) is int and type(frame.get('delivery_time_ms')) is int and
                 0 <= frame['capture_time_ms'] <= frame['delivery_time_ms'] <= now and
                 isinstance(frame.get('pose'),list) and len(frame['pose'])==3 and
                 all(type(v) in (float,int) and math.isfinite(v) for v in frame['pose']) and
                 isinstance(frame.get('ranges'),list) and len(frame['ranges'])==36 and
                 all(type(r) in (float,int) and math.isfinite(r) and 0 <= r <= 4 for r in frame['ranges']))
        if not valid:
            self.terminal(frame,'invalid',now)
        elif frame['event_id'] in self.seen:
            self.terminal(frame,'duplicate',now)
        else:
            self.seen.add(frame['event_id'])
            if len(self.queue)+bool(self.active) >= 10:
                self.terminal(frame,'queue_full',now)
            else:
                self.queue.append(frame)
                self.max_depth = max(self.max_depth,len(self.queue)+bool(self.active))

    def advance(self, now):
        if self.active and now >= self.active[2]:
            frame,start,finish = self.active
            self.mapper.apply(frame)
            self.terminal(frame,'processed',finish,service_start_ms=start,
                          age_at_use_ms=finish-frame['capture_time_ms'], map_version=self.mapper.version)
            self.active = None
        while not self.active and self.queue:
            frame = self.queue.popleft()
            if now-frame['capture_time_ms'] > 250:
                self.terminal(frame,'stale',now)
            else:
                self.active = (frame,now,now+self.service_ms)

    def finish(self, end):
        for now in range(end+10,end+1001,10):
            self.advance(now)
            if not self.active and not self.queue:
                return now
        if self.active:
            self.terminal(self.active[0],'censored',end+1000)
            self.active = None
        while self.queue:
            self.terminal(self.queue.popleft(),'censored',end+1000)
        return end+1000


def simulate(service_ms=10):
    config = json.loads(json.dumps(CONFIG))
    config['modeled_mapping_service_ms'] = service_ms
    mapper = Mapper(config)
    worker = Worker(mapper,service_ms)
    x,y = config['start']
    heading,vx,vy = 0.,0.,0.
    route,trace,frames = [],[],[]
    picked,delivered,collision = False,False,False
    minimum_clearance,path_length = float('inf'),0.
    stopped_ms,interventions,was_stopped,no_path_ticks = 0,0,False,0
    proximity = None
    for now in range(0,config['timeout_ms']+1,10):
        if now and now % 20 == 0:
            old = x,y
            # Independent sensor/interlock, sampled before every physics move.
            proximity = {'capture_time_ms':now, 'ranges':[
                sensor_range(x,y,heading+math.radians(a),config) for a in range(-30,31,10)]}
            stopped = stop_required(proximity,now)
            if stopped:
                stopped_ms += 20
                interventions += not was_stopped
            else:
                x,y = x+vx*.02,y+vy*.02
            was_stopped = stopped
            path_length += math.dist(old,(x,y))
        distance = clearance(x,y,config['walls'])-config['robot_radius_m']
        minimum_clearance = min(minimum_clearance,distance)
        if distance <= 0:
            collision = True
            trace.append({'time_ms':now,'x':x,'y':y,'heading':heading,'phase':'collision','queue_depth':len(worker.queue)+bool(worker.active)})
            break
        if not picked and math.dist((x,y),config['pickup']) <= .12:
            picked = True
        if picked and math.dist((x,y),config['destination']) <= .12:
            delivered = True
            trace.append({'time_ms':now,'x':x,'y':y,'heading':heading,'phase':'delivered','queue_depth':len(worker.queue)+bool(worker.active)})
            break
        worker.advance(now)
        if now % 50 == 0:
            frame = mapping_frame(len(frames),now,(x,y,heading),config)
            frames.append(frame)
            worker.offer(frame,now)
            worker.advance(now)
        if now % 500 == 0:
            route = mapper.path((x,y),config['destination'] if picked else config['pickup'])
        if now % 100 == 0:
            while route and math.dist((x,y),route[0]) < .08:
                route.pop(0)
            if route:
                dx,dy = route[0][0]-x,route[0][1]-y
                length = math.hypot(dx,dy)
                heading = math.atan2(dy,dx)
                speed = min(.5,length/.1)
                vx,vy = speed*dx/length,speed*dy/length
            else:
                vx,vy = 0.,0.
                no_path_ticks += 1
            trace.append({'time_ms':now,'x':x,'y':y,'heading':heading,
                          'phase':'deliver' if picked else 'pickup',
                          'queue_depth':len(worker.queue)+bool(worker.active),
                          'map_version':mapper.version,'interlock_stopped':was_stopped})
    mission_end = now
    drain_end = worker.finish(now)
    counts = Counter(e['outcome'] for e in worker.events)
    event_counts = Counter(e['event_id'] for e in worker.events)
    accounting = (len(worker.events)==len(frames) and len(event_counts)==len(frames) and
                  all(count==1 for count in event_counts.values()) and
                  set(event_counts)=={f['event_id'] for f in frames})
    summary = {'experiment':config['experiment'], 'scenario':'S01', 'arm':'R0',
               'status':'PASS' if delivered and not collision and accounting else 'FAIL',
               'delivered':delivered,'picked_up':picked,'collisions':int(collision),
               'mission_simulated_seconds':mission_end/1000, 'drain_end_ms':drain_end,
               'path_length_m':path_length,'minimum_clearance_m':minimum_clearance,
               'interlock_interventions':interventions,'interlock_stopped_seconds':stopped_ms/1000,
               'no_path_controller_ticks':no_path_ticks, 'frames_received':len(frames),
               'dispositions':dict(counts),'accounting_pass':accounting,'max_queue_depth':worker.max_depth,
               'map_observed_cells':len(mapper.observed),'map_version':mapper.version,
               'performance_claim':None,'full_robotics_spec_implemented':False,
               'limitations':['Static S01 only; no TiEE or R1 yet',
                   'Planner uses supplied static floor plan; sensor map does not yet drive navigation',
                   'No noise, dynamic obstacles, outages or physical dynamics',
                   'Service delays are modeled, not measured CPU time',
                   'No held-out evaluation or safety certification']}
    return config,summary,trace,frames,worker.events
