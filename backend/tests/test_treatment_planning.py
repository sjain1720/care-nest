import unittest
from datetime import date
from pydantic import ValidationError
from app.schemas import TreatmentPlanInput
from app.services.treatment_planning import prepare_plan


def facts():
    return {'productType':'health_indemnity', 'startDate':'2024-03-12',
            'waitingPeriods':[{'label':'Specific illness', 'appliesTo':'Cataract', 'endDate':'2026-03-12'}],
            'roomRent':{'label':'Normal room','amount':5000,'unit':'per day'},
            'coPay':{'label':'Conditional co-pay'}, 'deductible':{'label':'Not established'}}

class PlanningTests(unittest.TestCase):
    def test_missing_policy_asks_for_source(self):
        self.assertEqual(prepare_plan(TreatmentPlanInput(procedure='Cataract'),None).status,'needs_policy')
    def test_date_boundary_and_room_excess_are_calculated_not_coverage(self):
        result=prepare_plan(TreatmentPlanInput(procedure='Cataract',plannedAdmission=date(2026,3,12),normalRoomRatePerDay=7500),facts())
        self.assertEqual(result.waitingPeriods[0].dateStatus,'ends_by_planned_date')
        self.assertEqual(result.roomRisk.dailyExcess,2500)
        self.assertTrue(result.questionsToConfirm)
    def test_wait_not_over_one_day_before_end(self):
        result=prepare_plan(TreatmentPlanInput(procedure='Cataract',plannedAdmission=date(2026,3,11)),facts())
        self.assertEqual(result.waitingPeriods[0].dateStatus,'running_on_planned_date')
        self.assertEqual(result.waitingPeriods[0].daysRemainingAtAdmission,1)
    def test_unknown_end_or_planned_date_is_not_fabricated(self):
        result=prepare_plan(TreatmentPlanInput(procedure='Cataract'),facts())
        self.assertEqual(result.waitingPeriods[0].dateStatus,'planned_date_missing')
        f=facts();f['waitingPeriods'][0]['endDate']=''
        self.assertEqual(prepare_plan(TreatmentPlanInput(procedure='Cataract'),f).waitingPeriods[0].dateStatus,'end_date_unknown')
    def test_percentage_or_benefit_product_not_assumed_daily_rupee_limit(self):
        for field,value in [('productType','critical_illness'),('unit','%')]:
            f=facts()
            if field=='unit': f['roomRent']['unit']=value
            else: f[field]=value
            self.assertIsNone(prepare_plan(TreatmentPlanInput(procedure='Cataract',normalRoomRatePerDay=7500),f).roomRisk)
    def test_invalid_dates_and_rates_rejected(self):
        for params in ({'plannedAdmission':'2026-02-30'}, {'normalRoomRatePerDay':float('nan')}, {'normalRoomRatePerDay':-1}):
            with self.assertRaises(ValidationError): TreatmentPlanInput(procedure='Cataract',**params)
