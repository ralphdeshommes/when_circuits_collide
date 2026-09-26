import io
import unittest

import pandas as pd

from build_map import build_overlaps, build_projects, cluster_overlaps
from geocode import disambiguate
from overlaps import add_centers, find_overlaps, UTILITY_A, UTILITY_B


class PipelineTests(unittest.TestCase):
    def projects(self):
        return pd.DataFrame([
            dict(project_id='A', project_name='Alpha', utility=UTILITY_A, state='SC',
                 lat_a=33., lon_a=-81., lat_b=None, lon_b=None,
                 in_service_date='2026-01-01', location_confidence='sponsor_verified'),
            dict(project_id='B', project_name='Beta', utility=UTILITY_B, state='GA',
                 lat_a=33.01, lon_a=-81., lat_b=None, lon_b=None,
                 in_service_date='2026-01-11', location_confidence='manually_verified'),
        ])

    def test_empty_results_keep_csv_schema_and_zero_counts(self):
        df = self.projects()
        df.loc[1, 'lat_a'] = 35.
        pairs, projects = find_overlaps(df)
        restored = pd.read_csv(io.StringIO(pairs.to_csv(index=False)))
        self.assertEqual(build_overlaps(restored, {}), [])
        self.assertEqual(projects.overlap_count.tolist(), [0, 0])
        self.assertEqual(projects.overlap_1.tolist(), ['', ''])
        self.assertEqual(cluster_overlaps([]), 0)

    def test_incomplete_endpoints_cannot_invent_a_center(self):
        df = pd.DataFrame([dict(lat_a=33., lon_a=None, lat_b=None, lon_b=-81.),
                           dict(lat_a=33., lon_a=-81., lat_b=95., lon_b=-82.)])
        centers = add_centers(df)
        self.assertTrue(pd.isna(centers.loc[0, 'lat_center']))
        self.assertTrue(pd.isna(centers.loc[0, 'lon_center']))
        self.assertEqual(centers.loc[1, 'lat_center'], 33.)
        self.assertEqual(centers.loc[1, 'lon_center'], -81.)

    def test_verified_pair_and_partner_counts(self):
        pairs, projects = find_overlaps(self.projects())
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs.iloc[0]['time_gap (day)'], 10)
        self.assertEqual(pairs.iloc[0].confidence, 'verified')
        self.assertEqual(projects.overlap_count.tolist(), [1, 1])
        self.assertEqual(projects.overlap_1.tolist(), ['B', 'A'])

    def test_missing_date_has_actionable_error(self):
        df = self.projects()
        df.loc[0, 'in_service_date'] = None
        with self.assertRaisesRegex(ValueError, 'in_service_date'):
            find_overlaps(df)

    def test_disambiguation_stays_in_project_state(self):
        features = [dict(norm='TEST', state=state, lat=lat, lon=-81.)
                    for state, lat in [('GA', 33.), ('SC', 33.1), ('SC', 34.)]]
        match = disambiguate('TEST', 'SC', features, (33., -81.))
        self.assertEqual(match['state'], 'SC')
        self.assertEqual(match['lat'], 33.1)


if __name__ == '__main__':
    unittest.main()
