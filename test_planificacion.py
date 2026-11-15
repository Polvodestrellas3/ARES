import unittest
import atlas
from planificacion import mission, recommend, map_slope_pieces, metrics

class TestMission(unittest.TestCase):
    def setUp(self):
        self.routes=atlas.routes
        self.scale=atlas.terrain['metersPerPixel']
    def test_metrics(self):
        a,b=[metrics(r,self.scale) for r in self.routes]
        self.assertAlmostEqual(a['distance'],436.7,places=1)
        self.assertAlmostEqual(b['distance'],2204.88,places=1)
        self.assertAlmostEqual(a['max_slope'],6.33,places=2)
        self.assertAlmostEqual(b['max_slope'],15.75,places=2)
    def test_priorities(self):
        results=[mission(r,self.scale) for r in self.routes]
        self.assertEqual(recommend(results,'science'),1)
        self.assertEqual(recommend(results,'terrain'),0)
        self.assertEqual(recommend(results,'time'),0)
    def test_time_constraint(self):
        self.assertEqual(recommend([mission(r,self.scale,autonomy=120) for r in self.routes],'science'),0)
        self.assertIsNone(recommend([mission(r,self.scale,autonomy=15) for r in self.routes],'science'))
    def test_segments(self):
        for r in self.routes:
            self.assertEqual(len(map_slope_pieces(r,self.scale)),len(r['profile'])-1)
    def test_render(self):
        for params in [{},{'ruta':['1'],'capa':['pendientes'],'autonomy':['120']},{'speed':['nan']}]:
            self.assertIn('Recommended route',atlas.render(params))

if __name__=='__main__':unittest.main()
