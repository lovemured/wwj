#!/usr/bin/env python3
"""
模拟AI模型测试演示
无需真实API即可展示测试流程
"""

import json
import random
import time
from datetime import datetime

# 模拟的模型响应数据
MOCK_RESPONSES = {
    "中国的首都是哪里？": {
        "gpt-4": "北京。",
        "gpt-3.5": "中国的首都是北京。",
        "chatglm": "北京是中国的首都。",
        "deepseek": "北京。"
    },
    "5乘以3等于多少？": {
        "gpt-4": "5乘以3等于15。",
        "gpt-3.5": "结果是15。",
        "chatglm": "15。",
        "deepseek": "5 × 3 = 15"
    },
    "水的化学式是什么？": {
        "gpt-4": "H₂O",
        "gpt-3.5": "水的化学式是H2O。",
        "chatglm": "H2O（水分子由两个氢原子和一个氧原子组成）",
        "deepseek": "H2O"
    }
}

# 测试用例配置
TEST_CASES = [
    {
        "id": "TC-001",
        "description": "地理知识测试",
        "question": "中国的首都是哪里？",
        "assertions": [
            {"type": "contains", "value": "北京", "weight": 1.0}
        ]
    },
    {
        "id": "TC-002",
        "description": "数学计算测试",
        "question": "5乘以3等于多少？",
        "assertions": [
            {"type": "contains", "value": "15", "weight": 1.0}
        ]
    },
    {
        "id": "TC-003",
        "description": "科学知识测试",
        "question": "水的化学式是什么？",
        "assertions": [
            {"type": "similar", "value": "H2O", "threshold": 0.8, "weight": 1.0}
        ]
    }
]

# 待测试模型
MODELS = ["gpt-4", "gpt-3.5", "chatglm", "deepseek"]


def evaluate_response(response, assertion):
    """评估响应是否满足断言条件"""
    assertion_type = assertion["type"]
    expected_value = assertion["value"]

    if assertion_type == "contains":
        # 检查是否包含关键词
        return expected_value.lower() in response.lower()

    elif assertion_type == "similar":
        # 模拟相似度检查
        threshold = assertion.get("threshold", 0.8)
        # 简化：检查是否包含核心内容
        similarity = 1.0 if expected_value.lower() in response.lower() else 0.5
        return similarity >= threshold

    elif assertion_type == "exact":
        # 精确匹配
        return response.strip() == expected_value.strip()

    else:
        return False


def run_mock_evaluation():
    """运行模拟评测"""
    print("\n" + "="*60)
    print("   AI模型测试流程演示（模拟模式）")
    print("="*60)

    results = []
    start_time = time.time()

    # 执行测试
    for model in MODELS:
        print(f"\n正在测试模型: {model}")

        for test_case in TEST_CASES:
            question = test_case["question"]

            # 模拟API调用延迟
            latency = random.uniform(0.5, 2.0)
            time.sleep(0.1)  # 实际演示中的短暂延迟

            # 获取模拟响应
            response = MOCK_RESPONSES.get(question, {}).get(model, "模拟响应")

            # 评估断言
            assertion_results = []
            all_passed = True
            total_score = 0

            for assertion in test_case["assertions"]:
                passed = evaluate_response(response, assertion)
                score = assertion["weight"] if passed else 0
                total_score += assertion["weight"]

                assertion_results.append({
                    "type": assertion["type"],
                    "value": assertion["value"],
                    "passed": passed,
                    "score": score
                })

                if not passed:
                    all_passed = False

            # 记录结果
            result = {
                "model": model,
                "test_id": test_case["id"],
                "test_description": test_case["description"],
                "question": question,
                "response": response,
                "latency": latency,
                "cost": random.uniform(0.0001, 0.001),
                "passed": all_passed,
                "score": total_score / len(test_case["assertions"]),
                "assertion_results": assertion_results
            }

            results.append(result)

            # 打印单个测试结果
            status = "✅ PASS" if all_passed else "❌ FAIL"
            print(f"  {test_case['description']}: {status} (得分: {result['score']:.2f})")
            print(f"    问题: {question}")
            print(f"    回答: {response}")

    # 计算总体统计
    end_time = time.time()
    total_duration = end_time - start_time

    # 模型统计
    model_stats = {}
    for model in MODELS:
        model_results = [r for r in results if r["model"] == model]
        passed_count = sum(1 for r in model_results if r["passed"])
        avg_score = sum(r["score"] for r in model_results) / len(model_results)
        avg_latency = sum(r["latency"] for r in model_results) / len(model_results)
        avg_cost = sum(r["cost"] for r in model_results) / len(model_results)

        model_stats[model] = {
            "total_tests": len(model_results),
            "passed": passed_count,
            "failed": len(model_results) - passed_count,
            "pass_rate": passed_count / len(model_results),
            "avg_score": avg_score,
            "avg_latency": avg_latency,
            "avg_cost": avg_cost
        }

    # 生成报告
    report = {
        "summary": {
            "evaluation_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_models": len(MODELS),
            "total_tests": len(TEST_CASES) * len(MODELS),
            "total_passed": sum(1 for r in results if r["passed"]),
            "total_failed": sum(1 for r in results if not r["passed"]),
            "overall_pass_rate": sum(1 for r in results if r["passed"]) / len(results),
            "duration_seconds": round(total_duration, 2)
        },
        "model_analysis": model_stats,
        "detailed_results": results,
        "recommendations": generate_recommendations(model_stats)
    }

    # 保存报告
    output_file = "./results/mock_evaluation_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 打印详细报告
    print("\n" + "="*60)
    print("   评测报告")
    print("="*60)

    print("\n📊 总体统计:")
    print(f"   测试总数: {report['summary']['total_tests']}")
    print(f"   通过数量: {report['summary']['total_passed']}")
    print(f"   失败数量: {report['summary']['total_failed']}")
    print(f"   通过率: {report['summary']['overall_pass_rate']:.1%}")
    print(f"   测试耗时: {report['summary']['duration_seconds']}秒")

    print("\n📈 模型对比:")
    for model, stats in model_stats.items():
        print(f"\n   {model}:")
        print(f"     - 通过率: {stats['pass_rate']:.1%}")
        print(f"     - 平均得分: {stats['avg_score']:.2f}")
        print(f"     - 平均延迟: {stats['avg_latency']:.2f}秒")
        print(f"     - 平均成本: ${stats['avg_cost']:.4f}")

    print("\n💡 改进建议:")
    for i, rec in enumerate(report['recommendations'], 1):
        print(f"   {i}. {rec}")

    print("\n✅ 详细报告已保存至: " + output_file)
    print("\n" + "="*60)

    return report


def generate_recommendations(model_stats):
    """生成改进建议"""
    recommendations = []

    # 找出最佳模型
    best_model = max(model_stats.items(), key=lambda x: x[1]['avg_score'])
    recommendations.append(f"推荐使用模型: {best_model[0]} (平均得分: {best_model[1]['avg_score']:.2f})")

    # 成本效益分析
    cost_effective = min(model_stats.items(),
                        key=lambda x: x[1]['avg_cost'] / x[1]['avg_score'] if x[1]['avg_score'] > 0 else float('inf'))
    recommendations.append(f"性价比最高: {cost_effective[0]} (成本/得分: {cost_effective[1]['avg_cost']:.4f})")

    # 性能建议
    fastest = min(model_stats.items(), key=lambda x: x[1]['avg_latency'])
    recommendations.append(f"响应最快: {fastest[0]} (平均延迟: {fastest[1]['avg_latency']:.2f}秒)")

    return recommendations


if __name__ == '__main__':
    import os
    os.makedirs('./results', exist_ok=True)
    run_mock_evaluation()