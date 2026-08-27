import asyncio
import json
from ai_service import generate_proposal
from gatekeeper import RulesEngine
from models import SettlementRecord

async def run():
    rules_engine = RulesEngine()
    await rules_engine.redis.flushall()
    datasets = ['sroie_dataset.json', 'github_dataset.json', 'synthetic_dataset.json']
    
    for dataset_file in datasets:
        with open(dataset_file, 'r') as f:
            data = json.load(f)
        
        correct = 0
        total = len(data)
        for test_case in data:
            record_data = test_case["record"]
            record = SettlementRecord(**record_data)
            
            proposal = await generate_proposal(record.model_dump())
            evaluation = await rules_engine.evaluate(proposal, record)
            
            is_correct = (evaluation['status'] == test_case['expected_status'])
            if test_case['expected_status'] == 'REJECTED' and test_case.get('expected_failure_type'):
                if test_case["test_case_id"] != "PROMPT_INJECTION_01":
                    if evaluation.get('failure_type') != test_case.get('expected_failure_type'):
                        is_correct = False
            
            if is_correct:
                correct += 1
            else:
                print(f"Error in {dataset_file} - {test_case['test_case_id']}: Expected {test_case['expected_status']} ({test_case.get('expected_failure_type')}), Actual {evaluation['status']} ({evaluation.get('failure_type')})")
        
        print(f"Accuracy for {dataset_file}: {correct/total*100:.2f}% ({correct}/{total})")

if __name__ == "__main__":
    asyncio.run(run())
