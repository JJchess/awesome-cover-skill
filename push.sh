#!/bin/bash

# 检查是否提供了 commit message
if [ -z "$1" ]; then
  echo "❌ 错误: 请提供 commit message."
  echo "💡 用法: ./push.sh \"你的 commit message\""
  exit 1
fi

echo "📦 正在添加所有文件 (git add .)..."
git add .

echo "📝 正在提交代码..."
git commit -m "$1"

# 检查 commit 是否成功 (可能没有文件更改)
if [ $? -ne 0 ]; then
  echo "⚠️ 提交失败或没有文件发生更改。"
  exit 1
fi

echo "🚀 正在推送到远程仓库..."
git push

if [ $? -eq 0 ]; then
  echo "✅ 推送成功!"
else
  echo "❌ 推送失败，请检查网络或远程仓库状态。"
fi
