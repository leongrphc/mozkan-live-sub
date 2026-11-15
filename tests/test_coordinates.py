import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import QRect
from coordinates import NormalizedBox,normalized_region,screen_for_region


class Screen:
    def __init__(self,rect):
        self.rect=QRect(*rect)
    def geometry(self):
        return self.rect


class CoordinateTests(unittest.TestCase):
    def test_normalized_hud_uses_owning_monitor_with_negative_origin(self):
        screens=[Screen((-1920,100,1920,1080)),Screen((0,0,2560,1440))]
        self.assertEqual(normalized_region((-1728,316,384,108),screens).as_dict(),
                         dict(x=.1,y=.2,w=.2,h=.1))
        self.assertEqual(normalized_region((256,288,512,144),screens).as_dict(),
                         dict(x=.1,y=.2,w=.2,h=.1))

    def test_outside_or_spanning_monitors_never_falls_back_to_primary(self):
        screens=[Screen((-1920,0,1920,1080)),Screen((0,0,1920,1080))]
        for region in ((-20,100,40,50),(4000,100,200,50),(0,0,0,50),(False,0,100,50)):
            with self.subTest(region=region),self.assertRaises(ValueError):
                normalized_region(region,screens)
        with self.assertRaises(ValueError):
            normalized_region((100,100,200,50),[screens[1],Screen((0,0,1920,1080))])

    def test_wire_box_rejects_nonfinite_wrong_types_and_out_of_bounds(self):
        for value in (float('nan'),float('inf'),True,'0.2',10**500):
            with self.subTest(value=type(value).__name__),self.assertRaises(ValueError):
                NormalizedBox(value,.2,.3,.1)
        for box in ((.9,.2,.3,.1),(.2,.9,.1,.3),(.1,.1,0,.2),(-.1,.2,.2,.2)):
            with self.assertRaises(ValueError):
                NormalizedBox(*box)
        with self.assertRaises(ValueError):
            NormalizedBox.from_wire(dict(x=.1,y=.2,w=.3))
        source=dict(x=.1,y=.2,w=.3,h=.4)
        box=NormalizedBox.from_wire(source)
        source['x']=.7
        self.assertEqual(box.x,.1)
        self.assertEqual(box.as_dict(),dict(x=.1,y=.2,w=.3,h=.4))


if __name__=='__main__':
    unittest.main()
