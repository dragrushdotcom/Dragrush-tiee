import copy
import json
import unittest
from unittest.mock import patch

from benchmark.generator import generate
from shared.processor import canonical
from storage.postgres import Run, calculate, prepare


class StorageContractTests(unittest.TestCase):
    def setUp(self):
        self.event = next(generate(count=100))['event']

    def test_invalid_run_ids(self):
        for value in ('', 'a'*101, 'bad/run', None):
            with self.assertRaises(ValueError): Run(value)

    def test_invalid_arms(self):
        for value in ('B2', 'B3', 'unknown'):
            with self.assertRaises(ValueError): Run('test', value)

    def test_invalid_work_counts(self):
        for value in (-1, True, 10001, 0.1):
            with self.assertRaises(ValueError): Run('test', iterations=value)

    def test_canonical_replay_identity(self):
        self.assertEqual(prepare(canonical(self.event)), prepare(json.dumps(self.event, indent=2).encode()))

    def test_content_change_changes_hash(self):
        changed = copy.deepcopy(self.event)
        changed['payload']['quality'] = .81
        self.assertNotEqual(prepare(canonical(self.event))[1], prepare(canonical(changed))[1])

    def test_invalid_body_never_prepared(self):
        with self.assertRaises(ValueError): prepare(b'{}')

    def test_reject_has_no_output(self):
        self.event['payload']['quality'] = .79
        for arm in ('B0', 'B1', 'T'):
            state, decision, output = calculate(self.event, Run('test', arm, 0))
            self.assertEqual(state, 'REJECTED')
            self.assertIsNone(output)

    def test_accept_output_identical(self):
        self.event['payload']['quality'] = .80
        results = [calculate(self.event, Run('test', arm, 0))[2] for arm in ('B0', 'B1', 'T')]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    def test_late_filter_does_work_first(self):
        self.event['payload']['quality'] = .79
        with patch('storage.postgres.process', return_value={}) as process:
            calculate(self.event, Run('test','B0',0))
            process.assert_called_once()

    def test_early_filter_avoids_work(self):
        self.event['payload']['quality'] = .79
        with patch('storage.postgres.process') as process:
            for arm in ('B1','T'): calculate(self.event, Run('test',arm,0))
            process.assert_not_called()
