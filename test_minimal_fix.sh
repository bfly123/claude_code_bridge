#!/bin/bash
# 测试脚本：验证 OpenCode 和 Gemini 的最小修复

set -e

echo "=== CCB Multi 最小修复测试 ==="
echo ""

# 测试 1: OpenCode 第二次调用
echo "测试 1: OpenCode 第二次调用"
echo "----------------------------"
echo "第一次调用..."
CCB_CALLER=claude ask opencode "请回复：第一次测试成功" &
TASK1_PID=$!
sleep 5

echo "检查第一次调用结果..."
pend opencode || echo "第一次调用可能还在处理中"

echo ""
echo "第二次调用（关键测试）..."
CCB_CALLER=claude ask opencode "请回复：第二次测试成功" &
TASK2_PID=$!
sleep 5

echo "检查第二次调用结果..."
if pend opencode; then
    echo "✓ 第二次调用成功！"
else
    echo "✗ 第二次调用失败"
fi

echo ""
echo "----------------------------"
echo ""

# 测试 2: Gemini 稳定性
echo "测试 2: Gemini 连续调用"
echo "----------------------------"
SUCCESS_COUNT=0
TOTAL_COUNT=3

for i in {1..3}; do
    echo "Gemini 调用 $i/3..."
    CCB_CALLER=claude ask gemini "请回复：测试 $i 成功" &
    sleep 3

    if pend gemini; then
        echo "✓ 调用 $i 成功"
        ((SUCCESS_COUNT++))
    else
        echo "✗ 调用 $i 失败"
    fi
    echo ""
done

echo "----------------------------"
echo "Gemini 成功率: $SUCCESS_COUNT/$TOTAL_COUNT"
echo ""

# 测试 3: 降级检测（req_id 不匹配）
echo "测试 3: 降级完成检测"
echo "----------------------------"
echo "注意：这个测试会在日志中看到 WARN 消息，但应该仍然完成"
echo "检查日志文件以验证降级检测是否工作"
echo ""

# 总结
echo "=== 测试完成 ==="
echo ""
echo "预期结果："
echo "1. OpenCode 第二次调用应该成功（修复了会话 ID 固定问题）"
echo "2. Gemini 应该稳定返回（修复了降级检测）"
echo "3. 即使 req_id 不匹配，也应该能完成（降级模式）"
echo ""
echo "如果所有测试通过，说明最小修复成功！"
