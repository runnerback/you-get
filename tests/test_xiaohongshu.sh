#!/bin/bash

echo "=== 测试小红书图片下载功能 ==="
echo ""

# 测试URL
TEST_URL="http://sns-webpic-qc.xhscdn.com/202507311712/c5c6a7373e27cfe7788bb10fc2cff5e6/1040g2sg31kaovsncj0gg5panliui5q83kfp0t6o!nd_dft_wlteh_jpg_3"

# 创建测试输出目录
mkdir -p ./test_output

echo "1. 测试信息获取（不下载）："
echo "URL: $TEST_URL"
echo ""
you-get -i "$TEST_URL"

echo ""
echo "2. 测试实际下载："
you-get -o ./test_output "$TEST_URL"

echo ""
echo "=== 测试完成 ==="