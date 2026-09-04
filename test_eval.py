import pytest
import json
from ai_service import generate_proposal
from gatekeeper import RulesEngine
from models import SettlementRecord
import asyncio

def load_cases(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

all_cases = []
for dataset in ['sroie_dataset.json', 'github_dataset.json', 'synthetic_dataset.json']:
    cases = load_cases(dataset)
    for c in cases:
        c['_dataset'] = dataset
        all_cases.append(c)

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.mark.asyncio
@pytest.mark.parametrize("test_case", all_cases, ids=lambda x: f"{x['_dataset']}-{x['test_case_id']}")
async def test_evaluation(test_case):
    engine = RulesEngine()
    redis_client = await engine._get_redis()
    await redis_client.flushall()
    try:
        record_data = test_case["record"]
        record = SettlementRecord(**record_data)
        
        # 1. Generate Proposal
        proposal = await generate_proposal(record.model_dump())
        
        # 2. Gatekeeper Validates
        evaluation = await engine.evaluate(proposal, record)
        
        # 3. Assertions
        assert evaluation['status'] == test_case['expected_status']
        
        if test_case['expected_status'] == 'REJECTED' and test_case.get('expected_failure_type'):
            if test_case["test_case_id"] != "PROMPT_INJECTION_01":
                assert evaluation.get('failure_type') == test_case.get('expected_failure_type')
    finally:
        await redis_client.aclose()
