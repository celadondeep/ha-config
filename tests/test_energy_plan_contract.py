"""The same lease and target validation must protect both communication paths."""
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
import jinja2

ROOT=Path(__file__).resolve().parents[1]
if (ROOT/'work/custom_templates').exists():ROOT=ROOT/'work'


class PlanContract(unittest.TestCase):
    def setUp(self):
        self.t=1800000000.0
        self.attrs={'plan':{'actionable':'on','evaluated_at':self.t-10,'valid_until':self.t+170,
                          'inverter_on':'on','slot_active':'off','slot_cutoff_soc':'unknown'},
                    'health':{'last_checked':self.t-10}}
        self.states={'plan':'self_use','health':'ok'}
        self.env=jinja2.Environment(loader=jinja2.FileSystemLoader(ROOT/'custom_templates'))
        self.env.globals.update(now=lambda:datetime.fromtimestamp(self.t,timezone.utc),
            states=lambda entity:self.states[entity],state_attr=lambda entity,field:self.attrs[entity].get(field),
            as_timestamp=lambda x,default=0:x.timestamp() if isinstance(x,datetime) else float(x) if isinstance(x,(int,float)) else default)
        self.env.filters['to_json']=json.dumps

    def valid(self,floor=6):
        module=self.env.get_template('energy_plan.jinja').make_module()
        return json.loads(module.plan_valid('plan','health',floor,180))

    def test_live_unchanged_plan_uses_evaluation_lease(self):
        self.attrs['plan']['committed_at']=self.t-86400
        self.assertTrue(self.valid())

    def test_expired_plan(self):
        self.attrs['plan']['valid_until']=self.t-1
        self.assertFalse(self.valid())

    def test_stale_evaluation_with_fresh_health(self):
        self.attrs['plan']['evaluated_at']=self.t-181
        self.assertFalse(self.valid())

    def test_future_evaluation(self):
        self.attrs['plan']['evaluated_at']=self.t+61
        self.assertFalse(self.valid())

    def test_slot_requires_power(self):
        self.attrs['plan'].update(slot_active='on',slot_cutoff_soc=50,inverter_on='off')
        self.assertFalse(self.valid())

    def test_cutoff_respects_profile(self):
        self.attrs['plan'].update(slot_active='on',slot_cutoff_soc=10)
        self.assertTrue(self.valid(6));self.assertFalse(self.valid(13))

    def test_invalid_cutoff_rejected(self):
        for value in [None,True,'50',-1,101,float('nan')]:
            self.attrs['plan'].update(slot_active='on',slot_cutoff_soc=value)
            self.assertFalse(self.valid(),repr(value))

    def test_hold_and_manual_not_executable(self):
        for value in ['hold','manual','storm','unknown','unavailable']:
            self.states['plan']=value
            self.assertFalse(self.valid())

    def test_off_plan_without_slot_is_valid(self):
        self.attrs['plan']['inverter_on']='off'
        self.assertTrue(self.valid())

    def test_stale_health(self):
        self.attrs['health']['last_checked']=self.t-180
        self.assertFalse(self.valid())


if __name__=='__main__':unittest.main()
