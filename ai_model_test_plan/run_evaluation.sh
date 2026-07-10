#!/bin/bash

# AI模型评测执行脚本
# 使用Promptfoo进行多模型对比评测

echo "=========================================="
echo "   AI问答系统评测脚本"
echo "=========================================="

# 检查环境
echo ""
echo "Step 1: 检查环境..."

# 检查Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装，请先安装 Node.js"
    echo "   安装方法: brew install node"
    exit 1
fi
echo "✅ Node.js 已安装: $(node -v)"

# 检查Promptfoo
if ! command -v promptfoo &> /dev/null; then
    echo "⚠️  Promptfoo 未安装"
    echo "   正在安装..."
    npm install -g promptfoo
    if ! command -v promptfoo &> /dev/null; then
        echo "❌ Promptfoo 安装失败"
        exit 1
    fi
fi
echo "✅ Promptfoo 已安装: $(promptfoo --version)"

# 检查API密钥
echo ""
echo "Step 2: 检查API密钥..."
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  OPENAI_API_KEY 未设置"
    echo "   请设置: export OPENAI_API_KEY='your-api-key'"
    echo ""
    read -p "请输入你的OpenAI API Key: " api_key
    export OPENAI_API_KEY="$api_key"
fi
echo "✅ API密钥已设置"

# 创建结果目录
echo ""
echo "Step 3: 创建结果目录..."
mkdir -p ./results
echo "✅ 目录已创建"

# 运行评测
echo ""
echo "=========================================="
echo "Step 4: 开始运行评测..."
echo "=========================================="
echo ""

# 选项1: 快速测试（仅准确性测试）
echo "请选择测试模式:"
echo "  1. 快速测试（仅准确性，约5分钟）"
echo "  2. 完整测试（准确性+安全性，约15分钟）"
echo "  3. 自定义测试"
echo ""
read -p "请输入选项 (1/2/3): " mode

case $mode in
    1)
        echo "运行快速测试..."
        promptfoo eval --config promptfooconfig.yaml --filter "准确" --max-concurrency 3
        ;;
    2)
        echo "运行完整测试..."
        promptfoo eval --config promptfooconfig.yaml --max-concurrency 3
        ;;
    3)
        echo "自定义测试"
        read -p "请输入过滤条件（如：安全、业务、准确）: " filter
        promptfoo eval --config promptfooconfig.yaml --filter "$filter" --max-concurrency 3
        ;;
    *)
        echo "无效选项，运行完整测试..."
        promptfoo eval --config promptfooconfig.yaml --max-concurrency 3
        ;;
esac

echo ""
echo "=========================================="
echo "Step 5: 查看结果..."
echo "=========================================="
echo ""

# 打开Web界面查看结果
echo "是否打开Web界面查看详细结果？"
read -p "打开Web界面? (y/n): " open_web

if [[ "$open_web" == "y" || "$open_web" == "Y" ]]; then
    promptfoo view
else
    echo ""
    echo "结果文件位置:"
    echo "  - JSON: ./results/evaluation_results.json"
    echo "  - HTML: ./results/evaluation_results.html"
    echo ""
    echo "手动查看: promptfoo view"
fi

echo ""
echo "=========================================="
echo "   评测完成!"
echo "=========================================="
echo ""
echo "下一步:"
echo "  1. 查看详细报告: promptfoo view"
echo "  2. 分析结果数据: python analyze_results.py"
echo "  3. 导出报告: 打开 ./results/ 目录"
echo ""