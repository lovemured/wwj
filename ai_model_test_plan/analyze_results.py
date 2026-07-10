#!/usr/bin/env python3
"""
AI模型评测结果分析脚本
分析Promptfoo生成的JSON结果文件
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any


def load_results(filepath: str) -> Dict[str, Any]:
    """加载评测结果JSON文件"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"结果文件不存在: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_by_provider(results: List[Dict]) -> Dict[str, Dict]:
    """按模型分组统计"""
    provider_stats = {}

    for result in results:
        provider = result.get('provider', 'unknown')

        if provider not in provider_stats:
            provider_stats[provider] = {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'scores': [],
                'latencies': [],
                'costs': []
            }

        stats = provider_stats[provider]
        stats['total'] += 1

        if result.get('success', False):
            stats['passed'] += 1
        else:
            stats['failed'] += 1

        stats['scores'].append(result.get('score', 0))
        stats['latencies'].append(result.get('latency', 0))
        stats['costs'].append(result.get('cost', 0))

    # 计算平均值
    for provider, stats in provider_stats.items():
        total = stats['total']
        stats['pass_rate'] = stats['passed'] / total if total > 0 else 0
        stats['avg_score'] = sum(stats['scores']) / total if total > 0 else 0
        stats['avg_latency'] = sum(stats['latencies']) / total if total > 0 else 0
        stats['avg_cost'] = sum(stats['costs']) / total if total > 0 else 0

    return provider_stats


def analyze_by_category(results: List[Dict]) -> Dict[str, Dict]:
    """按测试类别分组统计"""
    category_stats = {}

    for result in results:
        # 从description中提取类别
        desc = result.get('test', {}).get('description', '')
        if '-' in desc:
            category = desc.split('-')[0]
        else:
            category = 'other'

        if category not in category_stats:
            category_stats[category] = {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'failed_cases': []
            }

        stats = category_stats[category]
        stats['total'] += 1

        if result.get('success', False):
            stats['passed'] += 1
        else:
            stats['failed'] += 1
            stats['failed_cases'].append({
                'test': desc,
                'provider': result.get('provider'),
                'reason': result.get('error', 'Unknown')
            })

    # 计算通过率
    for category, stats in category_stats.items():
        total = stats['total']
        stats['pass_rate'] = stats['passed'] / total if total > 0 else 0

    return category_stats


def analyze_failed_cases(results: List[Dict]) -> List[Dict]:
    """分析失败案例"""
    failed_cases = []

    for result in results:
        if not result.get('success', False):
            failed_cases.append({
                'provider': result.get('provider'),
                'test': result.get('test', {}).get('description', 'Unknown'),
                'input': result.get('vars', {}).get('question', ''),
                'output': result.get('output', ''),
                'score': result.get('score', 0),
                'assertion_failures': [
                    assertion for assertion in result.get('assertionResults', [])
                    if not assertion.get('passed', True)
                ]
            })

    return failed_cases


def generate_report(results_data: Dict, output_path: str = None):
    """生成分析报告"""

    results = results_data.get('results', [])

    # 分析统计
    provider_stats = analyze_by_provider(results)
    category_stats = analyze_by_category(results)
    failed_cases = analyze_failed_cases(results)

    # 构建报告
    report = {
        'summary': {
            'total_tests': len(results),
            'total_passed': sum(1 for r in results if r.get('success')),
            'total_failed': sum(1 for r in results if not r.get('success')),
            'overall_pass_rate': sum(1 for r in results if r.get('success')) / len(results) if results else 0,
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'provider_analysis': provider_stats,
        'category_analysis': category_stats,
        'failed_cases': failed_cases[:20],  # 只展示前20个失败案例
        'recommendations': generate_recommendations(provider_stats, category_stats, failed_cases)
    }

    # 输出
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✅ 报告已保存: {output_path}")

    return report


def generate_recommendations(provider_stats: Dict, category_stats: Dict, failed_cases: List) -> List[str]:
    """生成改进建议"""
    recommendations = []

    # 模型对比建议
    if len(provider_stats) > 1:
        best_provider = max(provider_stats.items(),
                          key=lambda x: x[1]['avg_score'])
        recommendations.append(f"推荐使用模型: {best_provider[0]} (平均得分: {best_provider[1]['avg_score']:.2f})")

        # 成本效益分析
        cost_effective = min(provider_stats.items(),
                            key=lambda x: x[1]['avg_cost'] / x[1]['avg_score'] if x[1]['avg_score'] > 0 else float('inf'))
        recommendations.append(f"性价比最高: {cost_effective[0]} (成本/得分: {cost_effective[1]['avg_cost']:.4f})")

    # 类别问题建议
    for category, stats in category_stats.items():
        if stats['pass_rate'] < 0.8:
            recommendations.append(f"类别 '{category}' 通过率较低 ({stats['pass_rate']:.1%}), 建议针对性优化")

    # 失败案例模式
    if failed_cases:
        failure_patterns = {}
        for case in failed_cases:
            test_type = case['test'].split('-')[0] if '-' in case['test'] else 'other'
            failure_patterns[test_type] = failure_patterns.get(test_type, 0) + 1

        most_failed = max(failure_patterns.items(), key=lambda x: x[1])
        recommendations.append(f"失败最多的类别: '{most_failed[0]}' ({most_failed[1]}次失败), 建议优先改进")

    return recommendations


def print_summary_report(report: Dict):
    """打印摘要报告"""
    print("\n" + "="*60)
    print("   AI模型评测分析报告")
    print("="*60)

    # 总体统计
    summary = report['summary']
    print("\n📊 总体统计:")
    print(f"   总测试数: {summary['total_tests']}")
    print(f"   通过数: {summary['total_passed']}")
    print(f"   失败数: {summary['total_failed']}")
    print(f"   通过率: {summary['overall_pass_rate']:.1%}")

    # 模型对比
    print("\n📈 模型对比:")
    for provider, stats in report['provider_analysis'].items():
        print(f"\n   {provider}:")
        print(f"     - 通过率: {stats['pass_rate']:.1%}")
        print(f"     - 平均得分: {stats['avg_score']:.2f}")
        print(f"     - 平均延迟: {stats['avg_latency']:.2f}s")
        print(f"     - 平均成本: $${stats['avg_cost']:.4f}")

    # 类别分析
    print("\n📂 类别分析:")
    for category, stats in report['category_analysis'].items():
        print(f"   {category}: {stats['pass_rate']:.1%} ({stats['passed']}/{stats['total']})")

    # 改进建议
    print("\n💡 改进建议:")
    for i, rec in enumerate(report['recommendations'], 1):
        print(f"   {i}. {rec}")

    # 失败案例（前5个）
    print("\n❌ 失败案例（前5个）:")
    for i, case in enumerate(report['failed_cases'][:5], 1):
        print(f"\n   {i}. {case['test']} ({case['provider']})")
        print(f"      输入: {case['input'][:50]}...")
        print(f"      输出: {case['output'][:100]}...")
        print(f"      得分: {case['score']:.2f}")

    print("\n" + "="*60)


def main():
    """主函数"""
    # 默认结果文件路径
    default_result_path = './results/evaluation_results.json'
    default_output_path = './results/analysis_report.json'

    # 允许用户指定路径
    if len(sys.argv) > 1:
        result_path = sys.argv[1]
    else:
        result_path = default_result_path

    if len(sys.argv) > 2:
        output_path = sys.argv[2]
    else:
        output_path = default_output_path

    try:
        # 加载结果
        print(f"📂 加载评测结果: {result_path}")
        results_data = load_results(result_path)

        # 生成报告
        report = generate_report(results_data, output_path)

        # 打印摘要
        print_summary_report(report)

    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        print("请先运行评测脚本: ./run_evaluation.sh")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 分析错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()