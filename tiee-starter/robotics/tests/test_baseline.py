import math
import unittest
from robotics.baseline import CONFIG, Mapper, Worker, clearance, mapping_frame, ray_box, stop_required


class RoboticsTests(unittest.TestCase):
    def test_ray_hit_and_miss(self):
        self.assertAlmostEqual(ray_box(1,1,1,0,(3,0,4,2)),2)
        self.assertTrue(math.isinf(ray_box(1,3,1,0,(3,0,4,2))))

    def test_collision_geometry(self):
        self.assertEqual(clearance(3.5,1,CONFIG['walls']),0)
        self.assertAlmostEqual(clearance(2.8,1,CONFIG['walls']),.2)

    def test_stale_proximity_fails_safe(self):
        self.assertTrue(stop_required(None,0))
        self.assertTrue(stop_required({'capture_time_ms':0,'ranges':[4]},101))
        self.assertTrue(stop_required({'capture_time_ms':0,'ranges':[.5]},0))
        self.assertFalse(stop_required({'capture_time_ms':0,'ranges':[4]},100))

    def test_no_diagonal_corner_cutting(self):
        mapper=Mapper(CONFIG)
        mapper.blocked={(2,1),(1,2)}
        path=mapper.path((.15,.15),(.25,.25))
        self.assertGreater(len(path),2)
        self.assertNotEqual(path[1],mapper.centre((2,2)))

    def test_queue_cap_and_staleness(self):
        mapper=Mapper(CONFIG);worker=Worker(mapper,100)
        for i in range(11):
            worker.offer(mapping_frame(i,0,(1,1,0),CONFIG),0)
        self.assertEqual(worker.events[0]['outcome'],'queue_full')
        self.assertEqual(worker.max_depth,10)
        worker.advance(260)
        self.assertEqual(sum(e['outcome']=='stale' for e in worker.events),10)

    def test_service_result_not_visible_early(self):
        mapper=Mapper(CONFIG);worker=Worker(mapper,50)
        worker.offer(mapping_frame(0,0,(1,1,0),CONFIG),0)
        worker.advance(0);worker.advance(40)
        self.assertEqual(mapper.version,0)
        worker.advance(50)
        self.assertEqual(mapper.version,1)
        self.assertEqual(worker.events[0]['age_at_use_ms'],50)

    def test_duplicate_and_invalid(self):
        worker=Worker(Mapper(CONFIG),10);frame=mapping_frame(0,0,(1,1,0),CONFIG)
        worker.offer(frame,0);worker.offer(frame,0)
        frame={**frame,'ranges':[float('nan')]*36}
        worker.offer(frame,0)
        self.assertEqual([e['outcome'] for e in worker.events],['duplicate','invalid'])
