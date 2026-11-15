import sys
import unittest
from pathlib import Path
from PySide6.QtCore import QRect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from regions import SelectedArea,Monitor,CapturePlan,read_saved_areas,save_areas


class Screen:
    def __init__(self,rect=(-1920,100,1920,1080),ratio=1.5):
        self.rect=QRect(*rect)
        self.ratio=ratio
    def geometry(self):return self.rect
    def devicePixelRatio(self):return self.ratio
    def name(self):return 'display'


class RegionsTests(unittest.TestCase):
    def test_wire_round_trip_retains_unknown_edid_and_detaches_caller_data(self):
        screen=Screen()
        area=SelectedArea.create((-1800,500,900,65),[screen])
        self.assertIsNone(area.monitor.serial)
        raw=save_areas(dict(subtitle=area))
        parsed,issues=read_saved_areas(raw)
        self.assertFalse(issues)
        self.assertEqual(parsed['subtitle'],area)
        raw['subtitle']['logical'][0]=200
        self.assertEqual(parsed['subtitle'].logical[0],-1800)
        self.assertIs(parsed['subtitle'].resolve([screen]),screen)

    def test_configuration_change_and_missing_or_ambiguous_owner_are_rejected(self):
        screen=Screen()
        area=SelectedArea.create((-1800,500,900,65),[screen])
        for screens in ([],[screen,Screen()],[Screen(ratio=2)],[Screen(rect=(-1920,0,1920,1080))]):
            with self.subTest(screens=screens),self.assertRaises(ValueError):
                area.resolve(screens)

    def test_invalid_role_does_not_discard_other_valid_role(self):
        area=SelectedArea.create((-1800,500,900,65),[Screen()])
        hud=SelectedArea.create((-1800,500,900,65),[Screen()],purpose='hud')
        raw=save_areas(dict(subtitle=area,hud=hud))
        raw['subtitle']['logical'][2]=True
        parsed,issues=read_saved_areas(raw)
        self.assertEqual(parsed,dict(hud=hud))
        self.assertEqual(len(issues),1)
        parsed,issues=read_saved_areas(dict(version=2,subtitle=None,hud=None))
        self.assertEqual(parsed,{})
        self.assertTrue(issues)

    def test_invalid_geometry_ratio_and_monitor_coverage_stay_invalid(self):
        area=SelectedArea.create((-1800,500,900,65),[Screen()])
        for ratio in (True,float('nan'),float('inf'),0,10**500):
            raw=area.to_wire()
            raw['monitor']['ratio']=ratio
            with self.subTest(ratio=type(ratio).__name__),self.assertRaises(ValueError):
                SelectedArea.from_wire(raw)
        raw=area.to_wire()
        raw['logical'][0]=5000
        with self.assertRaises(ValueError):SelectedArea.from_wire(raw)

    def test_running_plan_retains_live_screen_owner_and_physical_snapshot(self):
        screen=Screen()
        mapper=lambda region,screens:(region[0]*2,region[1]*2,region[2]*2,region[3]*2)
        plan=CapturePlan.create((-1800,500,900,65),(-1800,200,600,100),[screen],mapper)
        plan.validate([screen],mapper)
        self.assertEqual(plan.subtitle.physical,(-3600,1000,1800,130))
        with self.assertRaises(ValueError):plan.validate([Screen()],mapper)
        with self.assertRaises(ValueError):plan.validate([screen],lambda region,screens:region)
        screen.ratio=2
        with self.assertRaises(ValueError):plan.validate([screen])
