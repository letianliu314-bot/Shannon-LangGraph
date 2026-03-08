#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 释放 3000 端口（避免 EADDRINUSE）
lsof -ti :3000 2>/dev/null | xargs kill -9 2>/dev/null && sleep 1

# 优先使用 Node 20 LTS（兼容 Next.js 14）
NODE20="/opt/homebrew/opt/node@20/bin/node"
if [ -x "$NODE20" ]; then
  exec "$NODE20" "$DIR/node_modules/.bin/next" dev -p 3000
else
  exec node "$DIR/node_modules/.bin/next" dev -p 3000
fi
